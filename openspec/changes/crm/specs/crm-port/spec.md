# CRM Port Specification

## Purpose

Puerto de dominio `CRMClient` (hexagonal): contrato CRUD provider-agnostic sobre las entidades del pipeline Leads/demos (Lead/Person/Company/Opportunity), para que routers y workflows dejen de depender directamente de Airtable.

## Requirements

### Requirement: Contrato de operaciones del puerto

El sistema DEBE exponer una interfaz `CRMClient` con operaciones CRUD mínimas sobre la entidad `Lead` del pipeline de demos: `create_lead`, `get_lead`, `update_lead`, `find_lead`. Toda escritura desde `routers/calls.py` u otro llamador DEBE pasar por esta interfaz, nunca directamente por un SDK de proveedor.

#### Scenario: Crear un lead vía el puerto

- GIVEN un caller con los datos de un lead (nombre, email, empresa, teléfono, sector, fuente, estado, fecha de reunión, notas)
- WHEN invoca `CRMClient.create_lead(...)`
- THEN el puerto devuelve un identificador de lead y una URL/referencia al registro creado, independientemente del adaptador concreto activo

#### Scenario: Actualizar un lead existente

- GIVEN un `lead_id` válido y un subconjunto de campos a modificar
- WHEN invoca `CRMClient.update_lead(lead_id, fields)`
- THEN solo los campos provistos se sobreescriben; los campos ausentes u `None` NO se tocan en el registro remoto

#### Scenario: Patch parcial conserva los campos no incluidos

- GIVEN un lead existente con varios campos ya poblados (p.ej. `sector`, `notas`, `fecha_reunion`)
- WHEN se invoca `CRMClient.update_lead(ref, changes)` con un `LeadPatch` que solo incluye `estado` (el resto de campos quedan `None`/ausentes)
- THEN una llamada posterior a `CRMClient.get_lead(ref)` devuelve `estado` actualizado y el resto de campos (`sector`, `notas`, `fecha_reunion`, etc.) con su valor previo intacto, en ambos adaptadores (Airtable y Twenty)

#### Scenario: Buscar un lead existente por email o por Cal Booking ID

- GIVEN un `email` y/o un `cal_booking_id` provistos como criterio de búsqueda
- WHEN invoca `CRMClient.find_lead(email=..., cal_booking_id=...)`
- THEN el puerto devuelve el `LeadRef` del lead existente que matchea por email, o si no matchea por email pero sí por `cal_booking_id`, devuelve ese lead; si ningún criterio matchea, devuelve `None`

### Requirement: Independencia de proveedor en la firma

Los métodos del puerto NO DEBEN exponer tipos, IDs de base/tabla, ni estructuras de payload específicas de un proveedor (p.ej. `base_id` de Airtable o `objectMetadataId` de Twenty) en su firma pública. Cualquier detalle de proveedor se resuelve dentro del adaptador.

#### Scenario: Firma agnóstica de proveedor

- GIVEN el código cliente (`routers/calls.py`, workflow n8n) que usa `CRMClient`
- WHEN llama a cualquier método del puerto
- THEN no necesita conocer ni pasar `base_id`, nombre de tabla física, ni el esquema interno del proveedor activo

### Requirement: Manejo de errores uniforme

El puerto DEBE traducir errores de proveedor (HTTP 4xx/5xx, timeouts, validación de esquema) a una jerarquía de excepciones propia del dominio (p.ej. `CRMError`), de forma que el código llamador pueda manejar fallos sin conocer si el adaptador activo es Airtable o Twenty.

#### Scenario: Error de proveedor traducido

- GIVEN que el proveedor subyacente responde con un error (por ejemplo 422 o 5xx)
- WHEN el adaptador propaga el fallo a través del puerto
- THEN el caller recibe una excepción `CRMError` (o subclase) con mensaje y código de estado accesibles, no la excepción nativa del SDK del proveedor

### Requirement: Idempotencia en creación

`create_lead` DEBE ser idempotente usando el **email** como clave de identidad primaria (una `Person`/lead por humano), MÁS un **guardia por `calBookingId`**: si el email no matchea un lead existente pero el `calBookingId` sí, `create_lead` DEBE tratarlo como el mismo lead y no crear un duplicado. Esto cubre el caso de un reenvío del webhook de Cal.com con el mismo booking.

Esta idempotencia DEBE resolverse dentro del `create_lead` de **cada adaptador concreto** (invocando `find_lead` internamente antes de escribir), no únicamente en un compositor externo como `DualWriteCRMClient`. Motivo: tras el cutover, el adaptador activo puede operar sin que un compositor dual-write intermedie (p.ej. `CRM_BACKEND=twenty` puro, o como `primary` en el dual-write invertido post-cutover), y la idempotencia debe seguir garantizada en ese escenario.

#### Scenario: Reintento tras timeout no duplica el lead

- GIVEN una llamada previa a `create_lead` con un email dado que tuvo éxito pero cuya respuesta se perdió (timeout de red)
- WHEN el caller reintenta `create_lead` con el mismo email
- THEN el puerto devuelve el lead ya existente en lugar de crear un segundo registro

#### Scenario: Reenvío del webhook de Cal.com con el mismo booking no duplica el lead

- GIVEN un lead ya creado a partir de un `cal_booking_id` dado
- WHEN Cal.com reenvía el mismo webhook (mismo `cal_booking_id`, posiblemente con variaciones menores en el email o el payload)
- THEN `create_lead` detecta el lead existente vía el guardia por `calBookingId` y devuelve su `LeadRef` en lugar de crear un segundo registro

#### Scenario: La idempotencia se cumple con el adaptador operando en solitario (post-cutover)

- GIVEN un adaptador concreto (`AirtableCRMAdapter` o `TwentyCRMAdapter`) operando como único backend activo, sin `DualWriteCRMClient` de por medio
- WHEN se invoca `create_lead` dos veces con el mismo email o el mismo `cal_booking_id`
- THEN el adaptador, por sí mismo, devuelve el lead ya existente en la segunda llamada en lugar de crear un duplicado

### Requirement: Contrato compartido entre adaptadores

Todo adaptador que implemente `CRMClient` (Airtable, Twenty, o futuros) DEBE satisfacer el mismo contrato de entrada/salida, verificable mediante un test de contrato ligero compartido entre adaptadores.

#### Scenario: Test de contrato detecta divergencia

- GIVEN dos adaptadores (`AirtableCRMAdapter`, `TwentyCRMAdapter`) que implementan `CRMClient`
- WHEN se ejecuta el test de contrato ligero contra ambos con el mismo input
- THEN ambos devuelven una forma de respuesta compatible (mismos campos obligatorios: `lead_id`, `crm_url`) o el test falla señalando la divergencia
