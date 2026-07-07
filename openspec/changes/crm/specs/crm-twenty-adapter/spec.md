# CRM Twenty Adapter Specification

## Purpose

Adaptador `TwentyCRMAdapter` que satisface el puerto `CRMClient` (REST/GraphQL) contra una instancia de Twenty self-hosted, para el pipeline Leads/demos. **Person-only**: el piloto modela el lead exclusivamente como el objeto estándar `Person` de Twenty + campos custom; no crea `Company` ni `Opportunity`.

## Requirements

### Requirement: Conformidad con el puerto

`TwentyCRMAdapter` DEBE implementar íntegramente la interfaz `CRMClient` (`create_lead`, `get_lead`, `update_lead`, `find_lead`) traduciendo cada operación a llamadas REST/GraphQL contra la API de Twenty.

#### Scenario: Crear lead en Twenty vía el puerto

- GIVEN un `TwentyCRMAdapter` configurado con URL y API key de una instancia Twenty accesible
- WHEN se invoca `create_lead` con los datos de un lead
- THEN el adaptador crea (o reutiliza, ver idempotencia) el `Person` correspondiente en Twenty y devuelve un `lead_id` y `crm_url` válidos

#### Scenario: Buscar un lead en Twenty por email o Cal Booking ID

- GIVEN un `TwentyCRMAdapter` configurado contra una instancia Twenty con al menos un `Person` ya creado
- WHEN se invoca `find_lead(email=...)`, `find_lead(cal_booking_id=...)`, o ambos
- THEN el adaptador devuelve el `LeadRef` del `Person` que matchea por email o, en su defecto, por el custom field `calBookingId`; si ninguno matchea, devuelve `None`

### Requirement: Mapeo de campos del pipeline de demos

El adaptador DEBE mapear los campos actuales del lead de demos (nombre, email, empresa, teléfono, sector, fuente, estado, fecha de reunión, ID de booking de Cal.com, notas) a los campos estándar y custom del objeto **Person** en Twenty, sin pérdida de información respecto al modelo Airtable vigente. La empresa se mapea al campo custom de texto `companyName`; el piloto NO crea objetos `Company` ni `Opportunity`.

#### Scenario: Todos los campos del lead viajan a Twenty

- GIVEN un payload de lead con nombre, email, empresa, teléfono, sector, fuente, estado, fecha de reunión, ID de booking Cal.com y notas
- WHEN el adaptador ejecuta `create_lead`
- THEN cada uno de esos valores queda persistido en el campo equivalente del objeto `Person` (estándar o custom), consultable posteriormente vía `get_lead`

### Requirement: Traducción de errores de Twenty

El adaptador DEBE capturar errores HTTP/GraphQL de Twenty (autenticación, validación de esquema, rate limit, timeout) y re-lanzarlos como `CRMError` (o subclase) definida por el puerto, incluyendo código de estado y cuerpo de error original para debug.

#### Scenario: Twenty devuelve error de validación

- GIVEN que Twenty rechaza la creación de un lead por un campo requerido faltante o de tipo inválido
- WHEN el adaptador recibe la respuesta de error
- THEN lanza `CRMError` con el status code y el detalle del error de Twenty accesibles al caller, sin dejar escapar la excepción nativa del cliente HTTP/GraphQL

### Requirement: Idempotencia de create_lead dentro del adaptador

`TwentyCRMAdapter.create_lead` DEBE ejecutar internamente un pre-check con `find_lead` (por email y/o `calBookingId`) antes de crear un `Person` nuevo, de forma que el adaptador sea idempotente por sí mismo, sin depender de que `DualWriteCRMClient` lo proteja externamente. Esto es necesario porque, tras el cutover, `TwentyCRMAdapter` puede operar como único backend (`CRM_BACKEND=twenty`) o como `primary` del dual-write invertido, sin que ningún compositor intermedie.

#### Scenario: Reintento con la misma clave no crea un segundo Person

- GIVEN un `Person` ya creado en Twenty con un email y/o `calBookingId` dados
- WHEN se invoca `TwentyCRMAdapter.create_lead` de nuevo con el mismo email o el mismo `calBookingId`
- THEN el adaptador devuelve el `LeadRef` del `Person` existente (localizado vía `find_lead`) en lugar de crear un segundo `Person`

### Requirement: Patch parcial en update_lead

`TwentyCRMAdapter.update_lead` DEBE omitir del payload REST/GraphQL enviado a Twenty cualquier campo del `LeadPatch` que sea `None`, de forma que los campos no incluidos en la actualización conserven su valor remoto previo.

#### Scenario: Campos no incluidos conservan su valor tras el update

- GIVEN un `Person` en Twenty con `sector`, `notas` y `fechaReunion` ya poblados
- WHEN se invoca `TwentyCRMAdapter.update_lead(ref, changes)` con un `LeadPatch` que solo trae `estadoDemo` (el resto `None`)
- THEN el payload enviado a Twenty no incluye `sector`, `notas` ni `fechaReunion`, y una llamada posterior a `get_lead(ref)` los devuelve con su valor previo intacto

### Requirement: Normalización de valores heredados

`TwentyCRMAdapter` DEBE normalizar, antes de escribir, cualquier valor entrante de `sector` o `estado` que no exista como opción válida en los `SELECT` de Twenty (p.ej. valores heredados del workflow Meta que hoy dependen de `typecast` en Airtable), traduciéndolos a la opción equivalente más cercana del vocabulario cargado en Twenty. Esta normalización ocurre SOLO en `TwentyCRMAdapter`; `AirtableCRMAdapter` NUNCA normaliza ni reescribe estos valores.

#### Scenario: Valor de Sector inexistente en el SELECT se normaliza antes de escribir

- GIVEN un lead entrante con `Sector="Clínicas"` (valor que no existe como opción del `SELECT` `sector` en Twenty)
- WHEN `TwentyCRMAdapter` ejecuta `create_lead` o `update_lead` con ese lead
- THEN el adaptador normaliza `Sector` a la opción válida equivalente (p.ej. `Salud`) antes de enviar el payload a Twenty, y ese es el valor persistido

#### Scenario: Valor de Estado inexistente en el SELECT se normaliza antes de escribir

- GIVEN un lead entrante con `Estado="Nuevo"` (valor que no existe como opción del `SELECT` `estadoDemo` en Twenty)
- WHEN `TwentyCRMAdapter` ejecuta `create_lead` con ese lead
- THEN el adaptador normaliza `Estado` a un estado inicial válido del `SELECT` antes de escribir

#### Scenario: Airtable nunca normaliza estos valores

- GIVEN el mismo lead entrante con `Sector="Clínicas"` o `Estado="Nuevo"`
- WHEN el lead se escribe vía `AirtableCRMAdapter`
- THEN `AirtableCRMAdapter` escribe el valor tal cual (sin normalizar), preservando el comportamiento actual del flujo vivo

### Requirement: Autenticación configurable

El adaptador DEBE autenticar contra Twenty mediante API key/token configurado por variable de entorno, sin credenciales hardcodeadas, siguiendo el mismo patrón de configuración que el resto de servicios en `apps/api`.

#### Scenario: Adaptador sin credenciales configuradas falla rápido

- GIVEN que la variable de entorno con la API key de Twenty no está definida
- WHEN se intenta instanciar `TwentyCRMAdapter`
- THEN el adaptador falla de forma explícita al construirse (no en el primer request), con un mensaje que identifica la variable de entorno faltante

### Requirement: Test de contrato ligero

DEBE existir un test de contrato (pytest + respx, mockeando HTTP) que ejercite `TwentyCRMAdapter` contra las mismas aserciones de forma de respuesta usadas para `AirtableCRMAdapter`, verificando que ambos satisfacen el mismo contrato `CRMClient`, incluyendo `find_lead`, la idempotencia de `create_lead` y el patch parcial de `update_lead`. Este test NO sustituye la medición de paridad real (ver `crm-dual-write`); es una verificación barata de forma, no de datos reales en producción.

#### Scenario: Test de contrato pasa con HTTP mockeado

- GIVEN respx mockeando las respuestas HTTP de la API de Twenty
- WHEN se ejecuta el test de contrato ligero sobre `TwentyCRMAdapter`
- THEN el test verifica que la respuesta de `create_lead`/`get_lead`/`update_lead`/`find_lead` contiene los mismos campos obligatorios que produce `AirtableCRMAdapter`

#### Scenario: Test de contrato ejercita find_lead e idempotencia

- GIVEN respx mockeando Twenty y un mock equivalente de Airtable, ambos con un lead pre-existente
- WHEN el test de contrato invoca `find_lead` por email y por `calBookingId` contra ambos adaptadores, y luego reintenta `create_lead` con la misma clave
- THEN ambos adaptadores devuelven el `LeadRef` esperado en `find_lead` y ninguno crea un segundo registro al reintentar `create_lead`

#### Scenario: Test de contrato ejercita el patch parcial de update_lead

- GIVEN un lead existente en ambos adaptadores con varios campos poblados
- WHEN el test de contrato invoca `update_lead` con un `LeadPatch` parcial (un solo campo) contra ambos adaptadores y luego `get_lead`
- THEN en ambos adaptadores los campos no incluidos en el patch conservan su valor previo
