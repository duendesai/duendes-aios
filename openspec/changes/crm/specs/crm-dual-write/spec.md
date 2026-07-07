# CRM Dual-Write Specification

## Purpose

Escritura simultánea a Airtable y Twenty durante la fase de validación del piloto Leads/demos, con carga inicial (backfill) de los datos existentes, medición explícita de paridad, una puerta dura de backup/restore antes de declarar el cutover, y una ventana de seguridad post-cutover en dual-write invertido para que el rollback nunca pierda datos.

## Requirements

### Requirement: Backfill inicial de leads existentes

Antes de (o al inicio de) la ventana de dual-write en producción, el sistema DEBE cargar en Twenty, de forma idempotente y vía `TwentyCRMAdapter.create_lead`, los Leads/demos ya existentes en la base Airtable "Duendes CRM" (`appFIn3ntFb39vGXF`, tabla `Leads`). El backfill DEBE poder solaparse en el tiempo con leads nuevos que lleguen por dual-write sin generar duplicados, apoyándose en la idempotencia de `create_lead` (email + guardia `calBookingId`, ver spec `crm-port`).

#### Scenario: Backfill carga los leads existentes sin duplicar

- GIVEN la base Airtable "Duendes CRM" con Leads/demos ya existentes y Twenty recién desplegado (vacío)
- WHEN se ejecuta el backfill inicial contra `TwentyCRMAdapter`
- THEN cada lead de Airtable queda creado como `Person` en Twenty, y si el backfill se ejecuta más de una vez (o se solapa con un lead ya escrito por dual-write) no se generan duplicados

#### Scenario: Twenty no arranca vacío en el piloto

- GIVEN que el backfill se ha completado
- WHEN se consulta Twenty durante la ventana de dual-write
- THEN Twenty contiene el histórico de leads de Airtable además de los leads nuevos que van llegando, de forma que es un CRM usable desde el inicio del piloto

### Requirement: Orden y semántica de fallo en la escritura dual

Mientras el dual-write esté activo, el sistema DEBE escribir primero en Airtable (adaptador probado en producción) y, solo si tiene éxito, intentar Twenty (adaptador en validación). Si Airtable falla, el sistema NO DEBE escribir en Twenty y DEBE propagar el error como hoy sin dual-write. Si Airtable tiene éxito pero Twenty falla, el sistema DEBE registrar el fallo (log estructurado con lead_id/booking_id) sin bloquear ni revertir la escritura en Airtable ni la respuesta al caller.

#### Scenario: Twenty falla, Airtable ya escribió

- GIVEN que la escritura en Airtable se completó con éxito
- WHEN la escritura en Twenty falla (timeout, error de validación, etc.)
- THEN el sistema registra el fallo para reconciliación manual, y la respuesta al caller no cambia

#### Scenario: Airtable falla

- GIVEN que la escritura en Airtable falla
- WHEN el sistema evalúa si debe escribir en Twenty
- THEN NO escribe en Twenty y propaga el error de Airtable como hoy sin dual-write

### Requirement: Medición de paridad

El sistema DEBE proveer un mecanismo (script o job) que compare, para una ventana de tiempo dada, los leads creados en Airtable contra los creados en Twenty y reporte: número de leads en cada lado, discrepancias de campos por lead emparejado, y leads presentes en un lado pero ausentes en el otro.

#### Scenario: Reporte de paridad sin discrepancias

- GIVEN un conjunto de leads creados durante dual-write en una ventana de tiempo
- WHEN se ejecuta la medición de paridad
- THEN el reporte indica 100% de correspondencia y 0 discrepancias, condición necesaria (no suficiente) para autorizar el cutover

#### Scenario: Reporte de paridad con discrepancias

- GIVEN que algún lead existe en un solo lado o con valores distintos entre Airtable y Twenty
- WHEN se ejecuta la medición de paridad
- THEN el reporte identifica cada lead y campo discrepante, y el cutover NO se considera autorizado hasta resolver la causa

### Requirement: Puerta dura de backup y restore antes del cutover

El cutover a Twenty NO DEBE declararse hasta que exista (a) un backup automatizado y programado del Postgres de Twenty, y (b) al menos una restauración de ese backup ejecutada y verificada con éxito en un entorno separado de producción. Esta puerta es independiente de la paridad; ambas condiciones son necesarias. La verificación del restore DEBE comprobar, como mínimo: que las columnas/custom fields del objeto `Person` (`sector`, `fuente`, `estadoDemo`, `fechaReunion`, `calBookingId`, `notas`, `companyName`) existen tras el restore, y que 1-2 leads conocidos (localizados por email o `calBookingId`) reaparecen con los valores esperados de sector/fuente/estadoDemo/fechaReunion/notas. Un simple `count(Person) > 0` NO es suficiente para considerar el restore verificado.

#### Scenario: Cutover bloqueado sin restore probado

- GIVEN que el backup de Twenty está configurado pero nunca se ha restaurado y verificado
- WHEN se evalúa si el pipeline puede pasar a cutover
- THEN el cutover se considera NO autorizado, sin importar el resultado de la paridad

#### Scenario: Cutover bloqueado si el restore solo verifica conteo

- GIVEN que se restauró un backup en un entorno separado y se verificó únicamente que `count(Person) > 0`
- WHEN se evalúa si esa restauración satisface la puerta dura
- THEN NO se considera un restore verificado válido, porque no confirma la presencia de columnas/custom fields ni los valores reales de leads conocidos

#### Scenario: Restore verificado con columnas y valores de leads conocidos

- GIVEN que se restauró un backup en un contenedor Postgres efímero separado de producción
- WHEN se verifica que las columnas/custom fields de `Person` existen y que 1-2 leads conocidos (por email o `calBookingId`) reaparecen con sector/fuente/estadoDemo/fechaReunion/notas iguales a los valores esperados
- THEN el restore se considera verificado y satisface esta puerta dura

#### Scenario: Cutover autorizado

- GIVEN que el backup existe, una restauración de prueba se verificó con éxito (columnas + valores de leads conocidos), y la paridad reporta 0 discrepancias
- WHEN se decide el cutover
- THEN el pipeline Leads/demos puede reapuntar `CRMClient` a Twenty como `primary`, entrando en la ventana de seguridad de dual-write invertido (ver Requirement: Ventana de seguridad post-cutover)

### Requirement: Ventana de seguridad post-cutover (dual-write invertido)

Tras el cutover, el sistema NO DEBE pasar directamente a `CRM_BACKEND=twenty` puro. DEBE mantener, durante una ventana de seguridad, un dual-write **invertido**: `TwentyCRMAdapter` como `primary` y `AirtableCRMAdapter` como `secondary` (espejo). Airtable sigue recibiendo copia de toda escritura durante esta ventana, de forma que un rollback posterior al cutover nunca pierda datos. El espejo (dual-write invertido) solo se apaga, pasando a `CRM_BACKEND=twenty` puro, cuando Twenty es de plena confianza tras la ventana de seguridad.

#### Scenario: El cutover activa dual-write invertido, no Twenty puro

- GIVEN que se decide el cutover (paridad OK + puerta dura de backup/restore satisfecha)
- WHEN se aplica el cambio de configuración del cutover
- THEN `CRM_BACKEND` queda en modo dual con `primary=TwentyCRMAdapter` y `secondary=AirtableCRMAdapter`, no en `twenty` puro

#### Scenario: Airtable sigue recibiendo copia durante la ventana de seguridad

- GIVEN que el pipeline está en dual-write invertido tras el cutover
- WHEN se crea o actualiza un lead
- THEN el lead se escribe primero en Twenty (`primary`) y también en Airtable (`secondary`, con la misma semántica de fallo no bloqueante que tenía Twenty como `secondary` antes del cutover)

#### Scenario: El espejo se apaga solo cuando Twenty es de plena confianza

- GIVEN que la ventana de seguridad post-cutover transcurrió sin incidencias y Twenty se considera de plena confianza
- WHEN se decide desactivar el espejo
- THEN se reconfigura `CRM_BACKEND=twenty` puro, y Airtable deja de recibir escrituras duplicadas

### Requirement: Rollback trivial por configuración

El rollback DEBE ser siempre un cambio de configuración (qué adaptador resuelve `CRMClient`), sin requerir cambios en `routers/calls.py` ni en el workflow n8n del formulario Meta. El comportamiento del rollback difiere según el momento:

- **Rollback PRE-cutover** (durante el piloto, con Airtable como `primary` del dual-write): reapuntar `CRM_BACKEND=airtable` es trivial y sin pérdida de datos, porque Airtable nunca dejó de ser la fuente de verdad.
- **Rollback POST-cutover** (durante la ventana de seguridad de dual-write invertido, con Twenty como `primary`): reapuntar `CRM_BACKEND=airtable` (o `dual` con los roles originales) tampoco pierde datos, porque el dual-write invertido mantuvo a Airtable como espejo completo durante toda la ventana de seguridad.

#### Scenario: Rollback PRE-cutover no pierde datos

- GIVEN que el pipeline está en dual-write con Airtable como `primary` (piloto, antes del cutover)
- WHEN se decide revertir por un problema con Twenty
- THEN reconfigurar `CRMClient` al adaptador Airtable restaura el comportamiento previo sin desplegar cambios en routers o workflows, dado que Airtable nunca dejó de recibir todos los datos

#### Scenario: Rollback POST-cutover no pierde datos gracias al dual-write invertido

- GIVEN que el pipeline ya hizo cutover a Twenty y está en la ventana de seguridad de dual-write invertido (Twenty=primary, Airtable=secondary) cuando se detecta un problema grave
- WHEN se decide revertir
- THEN reconfigurar `CRMClient` para que Airtable vuelva a ser `primary` restaura el comportamiento previo sin desplegar cambios en routers o workflows, dado que Airtable recibió copia de todo durante la ventana de seguridad y no hay pérdida de datos
