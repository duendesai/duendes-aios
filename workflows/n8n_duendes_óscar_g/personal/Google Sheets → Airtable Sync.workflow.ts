import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Google Sheets → Airtable Sync
// Nodes   : 8  |  Connections: 5
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// CrearEnAirtable                    airtable                   [onError→regular] [creds]
// ActualizarEnAirtable               airtable                   [creds]
// EmailBienvenida                    gmail                      [creds]
// DescargarPdfRedFlags               googleDrive                [creds]
// GoogleSheetsTrigger                googleSheetsTrigger        [creds]
// BuscarDuplicadoAirtable            airtable                   [creds] [alwaysOutput]
// LeadNuevo                          if
// PrepararLeadDedupe                 code
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// GoogleSheetsTrigger
//    → BuscarDuplicadoAirtable
//      → PrepararLeadDedupe
//        → LeadNuevo
//          → CrearEnAirtable
//         .out(1) → ActualizarEnAirtable
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'Om22XDi7T02fya28',
    name: 'Google Sheets → Airtable Sync',
    active: true,
    settings: {
        timezone: 'Europe/Madrid',
        saveManualExecutions: true,
        executionTimeout: 7200,
        callerPolicy: 'workflowsFromSameOwner',
        availableInMCP: false,
        executionOrder: 'v1',
    },
})
export class GoogleSheetsAirtableSyncWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'b8c9d0e1-f2a3-4567-b8c9-d0e1f2a34567',
        name: 'Crear en Airtable',
        type: 'n8n-nodes-base.airtable',
        version: 2,
        position: [1152, 128],
        credentials: { airtableTokenApi: { id: 'x1uHjyxikVKPnKYS', name: 'Airtable account' } },
        onError: 'continueRegularOutput',
    })
    CrearEnAirtable = {
        operation: 'create',
        base: {
            __rl: true,
            value: 'appFIn3ntFb39vGXF',
            mode: 'list',
            cachedResultName: 'Duendes CRM',
            cachedResultUrl: 'https://airtable.com/appFIn3ntFb39vGXF',
        },
        table: {
            __rl: true,
            value: 'tblyTzWUXxpWeHJaB',
            mode: 'list',
            cachedResultName: 'Leads',
            cachedResultUrl: 'https://airtable.com/appFIn3ntFb39vGXF/tblyTzWUXxpWeHJaB',
        },
        columns: {
            mappingMode: 'autoMapInputData',
            value: {
                Estado: 'Nuevo',
                Fuente: 'Meta Ads',
                Sector: 'Wellness',
                Nombre: "={{ $json['Nombre'] }}",
                Email: "={{ $json['Email'] }}",
                Teléfono: "={{ $json['Teléfono'] || $json['Telefono'] || '' }}",
                Empresa: "={{ $json['Empresa'] }}",
            },
            matchingColumns: [],
            schema: [
                {
                    id: 'Nombre',
                    displayName: 'Nombre',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'string',
                    readOnly: false,
                    removed: false,
                },
                {
                    id: 'Email',
                    displayName: 'Email',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'string',
                    readOnly: false,
                    removed: false,
                },
                {
                    id: 'Teléfono',
                    displayName: 'Teléfono',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'string',
                    readOnly: false,
                    removed: true,
                },
                {
                    id: 'Empresa',
                    displayName: 'Empresa',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'string',
                    readOnly: false,
                    removed: true,
                },
                {
                    id: 'Fuente',
                    displayName: 'Fuente',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'options',
                    options: [
                        {
                            name: 'Meta Ads',
                            value: 'Meta Ads',
                        },
                        {
                            name: 'Web',
                            value: 'Web',
                        },
                        {
                            name: 'Referido',
                            value: 'Referido',
                        },
                        {
                            name: 'Outreach',
                            value: 'Outreach',
                        },
                        {
                            name: 'Otro',
                            value: 'Otro',
                        },
                        {
                            name: 'webinar',
                            value: 'webinar',
                        },
                    ],
                    readOnly: false,
                    removed: false,
                },
                {
                    id: 'Sector',
                    displayName: 'Sector',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'options',
                    options: [
                        {
                            name: 'Clínica Dental',
                            value: 'Clínica Dental',
                        },
                        {
                            name: 'Centro de Estética',
                            value: 'Centro de Estética',
                        },
                        {
                            name: 'Peluquería / Barbería',
                            value: 'Peluquería / Barbería',
                        },
                        {
                            name: 'Bufete / Legal',
                            value: 'Bufete / Legal',
                        },
                        {
                            name: 'Gestoría',
                            value: 'Gestoría',
                        },
                        {
                            name: 'Consultoría',
                            value: 'Consultoría',
                        },
                        {
                            name: 'Fontanería',
                            value: 'Fontanería',
                        },
                        {
                            name: 'Electricidad',
                            value: 'Electricidad',
                        },
                        {
                            name: 'Reformas',
                            value: 'Reformas',
                        },
                        {
                            name: 'Comercio',
                            value: 'Comercio',
                        },
                        {
                            name: 'Otro',
                            value: 'Otro',
                        },
                        {
                            name: 'Wellness',
                            value: 'Wellness',
                        },
                    ],
                    readOnly: false,
                    removed: false,
                },
                {
                    id: 'Estado',
                    displayName: 'Estado',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'options',
                    options: [
                        {
                            name: 'Nuevo',
                            value: 'Nuevo',
                        },
                        {
                            name: 'Contactado',
                            value: 'Contactado',
                        },
                        {
                            name: 'Reunión agendada',
                            value: 'Reunión agendada',
                        },
                        {
                            name: 'Propuesta enviada',
                            value: 'Propuesta enviada',
                        },
                        {
                            name: 'Negociación',
                            value: 'Negociación',
                        },
                        {
                            name: 'Ganado',
                            value: 'Ganado',
                        },
                        {
                            name: 'Perdido',
                            value: 'Perdido',
                        },
                        {
                            name: 'Incorrecto',
                            value: 'Incorrecto',
                        },
                        {
                            name: 'Recordatorio Enviado',
                            value: 'Recordatorio Enviado',
                        },
                    ],
                    readOnly: false,
                    removed: false,
                },
                {
                    id: 'Fecha reunión',
                    displayName: 'Fecha reunión',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'dateTime',
                    readOnly: false,
                    removed: true,
                },
                {
                    id: 'Cal Booking ID',
                    displayName: 'Cal Booking ID',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'string',
                    readOnly: false,
                    removed: true,
                },
                {
                    id: 'Notas',
                    displayName: 'Notas',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'string',
                    readOnly: false,
                    removed: true,
                },
                {
                    id: 'Convertido',
                    displayName: 'Convertido',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'boolean',
                    readOnly: false,
                    removed: false,
                },
                {
                    id: 'Clients',
                    displayName: 'Clients',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'array',
                    readOnly: false,
                    removed: true,
                },
                {
                    id: 'Próximo seguimiento',
                    displayName: 'Próximo seguimiento',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'dateTime',
                    readOnly: false,
                    removed: true,
                },
                {
                    id: 'Último contacto',
                    displayName: 'Último contacto',
                    required: false,
                    defaultMatch: false,
                    canBeUsedToMatch: true,
                    display: true,
                    type: 'dateTime',
                    readOnly: false,
                    removed: true,
                },
            ],
            attemptToConvertTypes: false,
            convertFieldsToString: false,
        },
        options: {},
    };

    @node({
        id: '5b0e72fd-0d71-4c74-8a91-2f95f4f8c681',
        name: 'Actualizar en Airtable',
        type: 'n8n-nodes-base.airtable',
        version: 2,
        position: [1792, -48],
        credentials: { airtableTokenApi: { id: 'x1uHjyxikVKPnKYS', name: 'Airtable account' } },
    })
    ActualizarEnAirtable = {
        operation: 'update',
        base: {
            __rl: true,
            value: 'appFIn3ntFb39vGXF',
            mode: 'list',
            cachedResultName: 'Duendes CRM',
            cachedResultUrl: 'https://airtable.com/appFIn3ntFb39vGXF',
        },
        table: {
            __rl: true,
            value: 'tblyTzWUXxpWeHJaB',
            mode: 'list',
            cachedResultName: 'Leads',
            cachedResultUrl: 'https://airtable.com/appFIn3ntFb39vGXF/tblyTzWUXxpWeHJaB',
        },
        columns: {
            mappingMode: 'defineBelow',
            value: {
                id: '={{ $json._airtable_id }}',
                Nombre: "={{ $json['Nombre'] }}",
                Email: "={{ $json['Email'] }}",
                Teléfono: "={{ $json['Teléfono'] || $json['Telefono'] || '' }}",
                Empresa: "={{ $json['Empresa'] }}",
            },
            matchingColumns: ['id'],
            schema: [],
        },
        options: {},
    };

    @node({
        id: 'c9d0e1f2-a3b4-5678-c9d0-e1f2a3b45678',
        webhookId: 'f9fcccd0-e3be-400b-a20e-5b90a0c4d2a8',
        name: 'Email Bienvenida',
        type: 'n8n-nodes-base.gmail',
        version: 2.1,
        position: [1600, 160],
        credentials: { gmailOAuth2: { id: 'nSVw510aT4Qwb1tQ', name: 'Gmail account' } },
    })
    EmailBienvenida = {
        sendTo: "={{ $('Crear en Airtable').item.json.fields.Email }}",
        subject: '✅ Bienvenido — Webinar IA + tu PDF RED FLAGS',
        message: `=<style>
  @import url('https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;600;700;800&family=Zilla+Slab:wght@400;600;700&display=swap');
</style>

<div style="max-width:640px; margin:0 auto; font-family:'Nunito Sans', Arial, Helvetica, sans-serif; color:#111111; text-align:center; overflow:hidden;">

  <img
    src="https://image2url.com/r2/default/images/1774954597380-cd60dfdd-78da-42b4-968b-7a8402fe54e0.png"
    alt="Duendes"
    style="display:block; width:100%; max-width:640px; height:auto; margin:0;"
  >

  <div style="padding:34px 32px 40px; text-align:center;">
    <h1 style="font-family:'Zilla Slab', Georgia, 'Times New Roman', serif; font-size:28px; line-height:1.2; margin:0 0 36px; font-weight:600; color:#111111;">
      Tu plaza está confirmada.
    </h1>

    <div style="text-align:left; font-family:'Nunito Sans', Arial, Helvetica, sans-serif; font-size:16px; line-height:1.8; color:#111111;">
      <p style="margin:0 0 18px;">Hola {{ $('Crear en Airtable').item.json.fields.Nombre }},</p>
      <p style="margin:0 0 18px;">gracias por apuntarte al webinar.</p>
      <p style="margin:0 0 18px;">Antes de nada, quiero dejarte clara una cosa:</p>
      <p style="margin:0 0 18px;">esta sesión no está pensada para que aprendas a automatizar procesos tú solo, ni para venderte un curso.</p>
      <p style="margin:0 0 18px;">El objetivo es mucho más simple y mucho más útil:</p>
      <p style="margin:0 0 18px;">que entiendas qué tipo de inteligencia artificial puede aportar valor real a tu empresa, en qué áreas tiene sentido aplicarla y cómo contratar este tipo de servicios con criterio, sin pagar de más ni comprar humo.</p>
      <p style="margin:0 0 18px;">Tal y como te prometí, y para que llegues al webinar con contexto, te adjunto en este mismo email el PDF:</p>
      <p style="margin:0 0 22px;"><strong>“RED FLAGS — Guía para evitar malas contrataciones de IA”</strong></p>
      <p style="margin:0 0 14px;">En el webinar vas a aprender a:</p>
      <ul style="margin:0 0 34px 22px; padding:0; line-height:1.9;">
        <li>distinguir oportunidades reales de simple marketing</li>
        <li>detectar en qué áreas de tu empresa puedes implementar IA ya mismo</li>
        <li>evaluar propuestas y presupuestos con más criterio</li>
        <li>entender qué pedir, qué evitar y cómo no sobredimensionar una solución que quizá no necesitas</li>
      </ul>
    </div>

    <div style="margin:42px 0 14px;">
      <div style="font-family:'Zilla Slab', Georgia, 'Times New Roman', serif; font-size:20px; line-height:1.3; margin-bottom:8px; color:#111111;">
        LA CLASE SERÁ EL DÍA
      </div>
      <div style="font-family:'Zilla Slab', Georgia, 'Times New Roman', serif; font-size:44px; line-height:1; font-weight:700; margin-bottom:10px; color:#111111;">
        8 DE ABRIL
      </div>
      <div style="font-family:'Zilla Slab', Georgia, 'Times New Roman', serif; font-size:20px; line-height:1.3; margin-bottom:8px; color:#111111;">
        A LAS
      </div>
      <div style="font-family:'Nunito Sans', Arial, Helvetica, sans-serif; font-size:42px; line-height:1; font-weight:800; margin-bottom:10px; color:#111111;">
        19:00
      </div>
      <div style="font-family:'Zilla Slab', Georgia, 'Times New Roman', serif; font-size:14px; line-height:1.4; color:#111111;">
        (HORA PENINSULAR)
      </div>
    </div>

    <div style="text-align:center; margin:34px 0 42px;">
      <div style="margin:0 0 20px;">
        <div style="font-family:'Zilla Slab', Georgia, 'Times New Roman', serif; font-size:18px; line-height:1.4; margin:0 0 8px; color:#111111;">
          AQUÍ TE DEJO EL LINK
        </div>
        <a href="https://meet.google.com/wta-qqcf-wdi?hs=224" style="font-family:'Nunito Sans', Arial, Helvetica, sans-serif; color:#1155cc; font-weight:800; font-size:17px; text-decoration:underline;">
          UNIRME A LA CLASE
        </a>
      </div>

      <div style="margin:0 0 32px;">
        <a href="https://calendar.google.com/calendar/r/eventedit?action=TEMPLATE&text=WEBINAR%20-%20C%C3%B3mo%20dar%20el%20salto%20a%20la%20Inteligencia%20Artificial&dates=20260408T170000Z%2F20260408T180000Z&stz=Europe%2FMadrid&etz=Europe%2FMadrid&details=Acceso%20a%20la%20clase%3A%20https%3A%2F%2Fmeet.google.com%2Fwta-qqcf-wdi%3Fhs%3D224%0A%0AV%C3%ADdeo%20de%20confirmaci%C3%B3n%3A%20https%3A%2F%2Fwww.duendes.net%2Fwebinar%2Fconfirmacion&location=https%3A%2F%2Fmeet.google.com%2Fwta-qqcf-wdi%3Fhs%3D224" style="font-family:'Nunito Sans', Arial, Helvetica, sans-serif; color:#1155cc; font-weight:800; font-size:17px; text-decoration:underline;">
          GUARDARLO EN MI CALENDARIO
        </a>
      </div>

      <div style="margin:0;">
        <div style="font-family:'Zilla Slab', Georgia, 'Times New Roman', serif; font-size:18px; line-height:1.4; margin:0 0 8px; color:#111111;">
          MIENTRAS TANTO PUEDES
        </div>
        <a href="https://www.duendes.net/webinar/confirmacion" style="font-family:'Nunito Sans', Arial, Helvetica, sans-serif; color:#1155cc; font-weight:800; font-size:17px; text-decoration:underline;">
          VER VÍDEO DE CONFIRMACIÓN
        </a>
      </div>
    </div>

    <div style="text-align:left; font-family:'Nunito Sans', Arial, Helvetica, sans-serif; font-size:16px; line-height:1.8; color:#111111;">
      <p style="margin:0 0 18px;">Por si no me conoces todavía, soy Óscar Graña, fundador de Duendes.</p>
      <p style="margin:0 0 18px;">Durante más de 10 años he trabajado dirigiendo equipos en áreas comerciales y de atención al cliente, y ahora mi foco está en acercar una visión útil y realista de la inteligencia artificial a autónomos y pymes.</p>
      <p style="margin:0 0 18px;">Gracias de nuevo por confiar en mí.</p>
      <p style="margin:0 0 10px;">Nos vemos en la clase.</p>
    </div>

    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:40px 0 0;">
      <tr>
        <td style="vertical-align:middle; padding-right:18px; width:90px;" align="left">
          <img
            src="https://image2url.com/r2/default/images/1774954623598-130f5ebc-e355-4888-bd77-bf68aab84362.png"
            alt="Óscar Graña"
            style="width:72px; height:72px; object-fit:cover; border-radius:50%; display:block;"
          >
        </td>
        <td style="vertical-align:middle; text-align:left;" align="left">
          <div style="font-family:'Nunito Sans', Arial, Helvetica, sans-serif; font-size:18px; font-weight:800; line-height:1.1; color:#111111;">
            ÓSCAR GRAÑA
          </div>
          <div style="font-family:'Nunito Sans', Arial, Helvetica, sans-serif; font-size:13px; color:#444444; margin-top:6px;">
            Fundador de Duendes · Agencia de IA
          </div>
          <div style="font-family:'Nunito Sans', Arial, Helvetica, sans-serif; font-size:13px; margin-top:6px;">
            <a href="mailto:hola@duendes.net" style="color:#111111; text-decoration:none;">hola@duendes.net</a>
          </div>
        </td>
      </tr>
    </table>
  </div>
</div>
`,
        options: {
            attachmentsUi: {
                attachmentsBinary: [{}],
            },
        },
    };

    @node({
        id: '08d31608-30c2-4458-a863-3d398efa89cd',
        name: 'Descargar PDF RED FLAGS',
        type: 'n8n-nodes-base.googleDrive',
        version: 3,
        position: [1376, 160],
        credentials: { googleDriveOAuth2Api: { id: 'qPlXGvCZDKaXn4go', name: 'Google Drive account' } },
    })
    DescargarPdfRedFlags = {
        operation: 'download',
        fileId: {
            __rl: true,
            value: '1V86-XtB7f2UQl_zGPXgG5cuFlOdkDl08',
            mode: 'list',
            cachedResultName: 'RED FLAGS - Guía de contratación de IA para empresas - duendes.pdf',
            cachedResultUrl: 'https://drive.google.com/file/d/1V86-XtB7f2UQl_zGPXgG5cuFlOdkDl08/view?usp=drivesdk',
        },
        options: {
            fileName: 'RED FLAGS - Guía para evitar malas contrataciones de IA.pdf',
        },
    };

    @node({
        id: '2ee56df2-0767-47fd-b9d4-4f52f5af34ca',
        name: 'Google Sheets Trigger',
        type: 'n8n-nodes-base.googleSheetsTrigger',
        version: 1,
        position: [912, -48],
        credentials: { googleSheetsTriggerOAuth2Api: { id: 'fiQknqBGuatfImCX', name: 'Google Sheets Trigger' } },
    })
    GoogleSheetsTrigger = {
        pollTimes: {
            item: [
                {
                    mode: 'everyMinute',
                },
            ],
        },
        documentId: {
            __rl: true,
            mode: 'id',
            value: '=1htYJWJ9lF4qMz0cdjzoNbIATFmYgaeYRo2pTy77CsPU',
        },
        sheetName: {
            __rl: true,
            value: 2134059263,
            mode: 'list',
            cachedResultName: 'Leads-Grid view',
            cachedResultUrl:
                'https://docs.google.com/spreadsheets/d/1htYJWJ9lF4qMz0cdjzoNbIATFmYgaeYRo2pTy77CsPU/edit#gid=2134059263',
        },
        event: 'rowAdded',
        options: {},
    };

    @node({
        id: '1e192089-176a-4cb5-80ef-d7cb66ed8f1f',
        name: 'Buscar duplicado Airtable',
        type: 'n8n-nodes-base.airtable',
        version: 2,
        position: [1152, -48],
        credentials: { airtableTokenApi: { id: 'x1uHjyxikVKPnKYS', name: 'Airtable account' } },
        alwaysOutputData: true,
    })
    BuscarDuplicadoAirtable = {
        operation: 'search',
        base: {
            __rl: true,
            value: 'appFIn3ntFb39vGXF',
            mode: 'list',
            cachedResultName: 'Duendes CRM',
            cachedResultUrl: 'https://airtable.com/appFIn3ntFb39vGXF',
        },
        table: {
            __rl: true,
            value: 'tblyTzWUXxpWeHJaB',
            mode: 'list',
            cachedResultName: 'Leads',
            cachedResultUrl: 'https://airtable.com/appFIn3ntFb39vGXF/tblyTzWUXxpWeHJaB',
        },
        filterByFormula:
            '={{ "LOWER({Email})=\\"" + String($(\'Google Sheets Trigger\').itemMatching(0).json[\'Email\'] || "").toLowerCase().replace(/"/g, \'\\\\"\') + "\\"" }}',
        returnAll: false,
        limit: 1,
        options: {},
    };

    @node({
        id: '99c44458-75db-4212-b229-f055492ec2cc',
        name: '¿Lead nuevo?',
        type: 'n8n-nodes-base.if',
        version: 2,
        position: [1568, -48],
    })
    LeadNuevo = {
        conditions: {
            options: {
                caseSensitive: true,
                leftValue: '',
                typeValidation: 'strict',
                version: 1,
            },
            conditions: [
                {
                    id: 'cond-is-new-sheet-lead',
                    leftValue: '={{ $json._airtable_id || "" }}',
                    rightValue: '',
                    operator: {
                        type: 'string',
                        operation: 'equals',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: 'e151012b-298d-4735-88f7-91ce925631ce',
        name: 'Preparar lead dedupe',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1360, -48],
    })
    PrepararLeadDedupe = {
        jsCode: `const items = $input.all();

for (let i = 0; i < items.length; i++) {
  const source = $('Google Sheets Trigger').itemMatching(i).json;
  const existing = items[i].json || {};

  items[i].json = {
    Nombre: source['Nombre'] || '',
    Email: source['Email'] || '',
    'Teléfono': source['Teléfono'] || source['Telefono'] || '',
    Empresa: source['Empresa'] || '',
    Fuente: source['Fuente'] || '',
    Sector: source['Sector'] || '',
    Estado: source['Estado'] || '',
    'Fecha reunión': source['Fecha reunión'] || '',
    'Cal Booking ID': source['Cal Booking ID'] || '',
    Notas: source['Notas'] || '',
    Convertido: source['Convertido'] || '',
    Clients: source['Clients'] || '',
    'Próximo seguimiento': source['Próximo seguimiento'] || '',
    'Último contacto': source['Último contacto'] || '',
    id: source['id'] || '',
    created_time: source['created_time'] || '',
    ad_id: source['ad_id'] || '',
    ad_name: source['ad_name'] || '',
    adset_id: source['adset_id'] || '',
    adset_name: source['adset_name'] || '',
    campaign_id: source['campaign_id'] || '',
    campaign_name: source['campaign_name'] || '',
    _airtable_id: existing.id || '',
    _airtable_exists: !!existing.id,
  };
}

return items;`,
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.GoogleSheetsTrigger.out(0).to(this.BuscarDuplicadoAirtable.in(0));
        this.BuscarDuplicadoAirtable.out(0).to(this.PrepararLeadDedupe.in(0));
        this.LeadNuevo.out(0).to(this.CrearEnAirtable.in(0));
        this.LeadNuevo.out(1).to(this.ActualizarEnAirtable.in(0));
        this.PrepararLeadDedupe.out(0).to(this.LeadNuevo.in(0));
    }
}
