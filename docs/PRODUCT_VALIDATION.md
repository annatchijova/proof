

# PROOF — Product Validation / Validación de Producto

**Argentina Builder Challenge · BAF × Stellar · Genesis Track**

## English

### 1. Problem Validation

#### The problem

A payment screenshot, message, or transaction reference can be presented as evidence that a payment occurred. However, the representation of a payment is not the payment itself.

For payments executed on Stellar, the ledger contains independently inspectable facts about what actually occurred. A recipient, merchant, freelancer, platform, auditor, or dispute participant may therefore need to answer a more precise question:

> **Did the payment being claimed actually occur on the Stellar ledger under the stated conditions?**

PROOF converts that question into explicit, independently checkable propositions.

Instead of asking whether a screenshot *looks legitimate*, PROOF evaluates claims such as:

* Does the referenced transaction exist?
* Did it succeed?
* Was the expected sender involved?
* Did the expected recipient receive the payment?
* Was the expected asset transferred?
* Was the expected amount transferred?
* Does the transaction contain the expected reference or memo?
* Does the evidence support the entire claim, contradict part of it, or remain insufficient?

#### Who has this problem?

The initial user groups we are evaluating are:

* people receiving payments who need to verify a payment claim;
* merchants and service providers receiving Stellar payments;
* platforms that need machine-verifiable payment verification;
* people involved in payment disputes;
* auditors or investigators reconstructing payment events.

These are **candidate user groups**, not yet claims of validated demand.

#### Current validation status

**Problem validation is in progress.**

The project will record real conversations separately rather than presenting assumptions as validation.

For each conversation we want to establish:

1. whether the person encounters payment claims that require independent verification;
2. how they verify them today;
3. what information matters when deciding whether the claimed payment occurred;
4. where the current process fails or creates friction;
5. whether independently reproducible verification would improve that workflow.

**Evidence collected:** *pending*

**Conversations completed:** *pending*

**Observed recurring problems:** *pending*

This section will be updated only with findings actually observed during validation.

---

### 2. Business Focus

#### Value proposition

> **Don’t trust the screenshot. Verify the payment.**

PROOF turns a payment claim into a deterministic verification against Stellar ledger evidence.

The product is not primarily a block explorer. A block explorer answers:

> “What happened in this transaction?”

PROOF answers a different question:

> “Does what happened support this specific payment claim?”

That distinction allows verification to become a reusable service rather than a manual inspection process.

#### Potential adoption paths

PROOF is currently designed around two complementary modes:

**Human verification**

A user supplies a Stellar transaction and the payment conditions they expect. PROOF returns a bounded verdict and the evidence behind it.

**Machine-to-machine verification**

The HTTP API and MCP interface allow other systems or agents to request the same deterministic verification without implementing the adjudication logic themselves.

Potential integration contexts include payment platforms, marketplaces, commerce systems, accounting/reconciliation workflows, dispute systems, agents, and forensic tooling.

These are **potential markets and integration paths**. Commercial demand has not yet been established.

#### Growth path

The initial product deliberately addresses a narrow claim:

**verification of a Stellar payment claim.**

The architecture can later support more complex ledger claims without changing the fundamental model:

```text
claim
  ↓
ledger evidence
  ↓
deterministic adjudication
  ↓
verifiable result
```

Expansion is justified only where the same verification problem exists. The hackathon implementation is not presented as evidence that every adjacent use case has market demand.

---

### 3. Product Focus

#### Primary user journey

PROOF is designed around one complete task:

> **I was told that this payment occurred. Verify it.**

The user provides:

1. a Stellar transaction hash;
2. the Stellar network;
3. any payment properties they want to assert, such as sender, recipient, asset, amount, or reference.

PROOF acquires the ledger evidence and evaluates each asserted proposition independently.

The result is one of three states:

**VERIFIED**

The available ledger evidence supports every required proposition in the payment claim.

**NOT VERIFIED**

The ledger was successfully inspected, but at least one required proposition is contradicted by the evidence.

**INSUFFICIENT EVIDENCE**

PROOF cannot obtain or establish enough evidence to support or contradict the claim safely.

This distinction prevents acquisition failure from being represented as payment failure.

#### What the product does not claim

PROOF verifies **ledger evidence**, not facts outside the ledger.

Therefore:

* payment executed ≠ debt legally satisfied;
* transaction exists ≠ goods were delivered;
* wallet authorization ≠ human identity;
* on-chain commitment ≠ underlying claim is true;
* absence of sufficient evidence ≠ evidence that the payment did not occur.

These boundaries are part of the product behavior rather than disclaimer text added after adjudication.

#### User-facing complexity

The primary interface exposes payment concepts rather than implementation concepts.

A user does not need to understand canonical serialization, evidence-bundle schemas, cryptographic sealing, Horizon/RPC internals, or Soroban to verify a claim.

Technical evidence remains available for independent inspection.

---

### 4. Technical Execution

PROOF separates acquisition, evidence, adjudication, integrity, and presentation.

```text
Stellar
   │
   ▼
ledger acquisition
   │
   ▼
structured evidence
   │
PaymentClaim
   │
   ▼
deterministic adjudication
   │
   ├── VERIFIED
   ├── NOT VERIFIED
   └── INSUFFICIENT EVIDENCE
   │
   ▼
sealed EvidenceBundle
   │
   ├── independent verification
   └── Stellar/Soroban commitment
```

#### Deterministic core

The verification result is produced by deterministic application logic rather than an LLM.

The same claim and the same normalized evidence must produce the same adjudication and sealed representation.

External acquisition is treated separately: fetching data from Stellar is an external observation and is not falsely described as deterministic.

#### Evidence integrity

PROOF produces a versioned evidence bundle containing the claim, acquired evidence, individual checks, verdict, and applicable scope information.

The sealed representation is canonicalized and hashed so modification after sealing can be detected.

An independent verification path can recompute the seal without relying on the adjudication workflow that originally produced the result.

#### Stellar integration

Stellar is not an ornamental integration. The ledger is the authoritative source from which PROOF reconstructs the payment evidence being evaluated.

The product is being validated end-to-end against **real Stellar Testnet transactions**, rather than relying solely on fixtures or mocked ledger responses.

#### Soroban

PROOF additionally uses Soroban to create an on-chain commitment to a sealed evidence result.

The intended separation is:

```text
PROOF deterministic engine
→ determines what the acquired evidence supports

Soroban
→ establishes an on-chain commitment and provenance
  for a particular sealed result
```

The existence of a Soroban commitment **does not mean that the contract independently determined that the payment claim is true**.

That distinction is an explicit trust boundary.

#### Current implementation status

At the time of this document:

* deterministic payment-claim adjudication: **implemented**;
* canonical evidence bundles and cryptographic sealing: **implemented**;
* independent verification: **implemented**;
* multi-operation transaction handling: **implemented**;
* dispute handling for contradictory claims: **implemented**;
* HTTP API: **implemented**;
* MCP interface: **implemented**;
* Soroban contract: **deployed and validated on Stellar Testnet**;
* adversarial/red-team review: **performed; identified findings addressed**;
* automated test suite: covered by the repository's test command; the current
  count is intentionally not hard-coded here;
* public deployment: **deployed on Google Cloud Run**;
* real-user problem validation: **pending**.

These statuses should be updated as evidence changes.

#### Reproducible Testnet evidence

The full end-to-end path was validated against real Stellar Testnet data:

* Payment transaction: `0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669`
* Payment ledger: `4821215`
* PROOF verdict: `VERIFIED`
* Evidence seal: `c6d21734805d59886bc9a629893eb108a0666c74a03ed6e19e5abdc50e1b7d51`
* Soroban registry contract: `CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I`
* Commitment ledger: `4821217`
* Receipt ledger: `4821218`

The sealed evidence bundle was independently verified, tampering was detected
after mutation, and the on-chain commitment and receipt were retrieved from
the deployed Soroban contract.

---

# Español

### 1. Validación del problema

#### El problema

Una captura de pago, un mensaje o una referencia de transacción pueden presentarse como evidencia de que un pago ocurrió. Sin embargo, **la representación de un pago no es el pago**.

Cuando el pago se ejecutó sobre Stellar, el ledger contiene hechos que pueden inspeccionarse independientemente. Un receptor, comercio, profesional, plataforma, auditor o participante de una disputa puede necesitar responder una pregunta más precisa:

> **¿El pago que se afirma realmente ocurrió en el ledger de Stellar bajo las condiciones declaradas?**

PROOF convierte esa pregunta en proposiciones explícitas y verificables independientemente.

En lugar de determinar si una captura *parece legítima*, PROOF contrasta afirmaciones como:

* ¿Existe la transacción indicada?
* ¿Fue exitosa?
* ¿Participó el emisor esperado?
* ¿El receptor esperado recibió el pago?
* ¿Se transfirió el activo esperado?
* ¿Se transfirió el monto esperado?
* ¿La transacción contiene la referencia o memo esperado?
* ¿La evidencia respalda la afirmación completa, contradice una parte o resulta insuficiente?

#### ¿Quién tiene este problema?

Los grupos iniciales que estamos evaluando incluyen:

* personas que reciben pagos y necesitan verificar una afirmación de pago;
* comercios y prestadores de servicios que reciben pagos mediante Stellar;
* plataformas que necesitan verificación de pagos procesable por máquinas;
* participantes de disputas sobre pagos;
* auditores o investigadores que reconstruyen eventos de pago.

Estos son **grupos de usuarios candidatos**, no demanda validada.

#### Estado de validación

**La validación del problema está en curso.**

Las conversaciones reales se registrarán como evidencia separada en lugar de presentar supuestos como validación.

Buscamos establecer:

1. si la persona encuentra afirmaciones de pago que requieren verificación independiente;
2. cómo las verifica actualmente;
3. qué información necesita comprobar;
4. dónde falla o genera fricción el proceso actual;
5. si una verificación reproducible independientemente mejoraría ese flujo.

**Evidencia recopilada:** *pendiente*

**Conversaciones realizadas:** *pendiente*

**Problemas recurrentes observados:** *pendiente*

---

### 2. Foco de negocio

#### Propuesta de valor

> **No confíes en la captura. Verificá el pago.**

PROOF transforma una afirmación de pago en una verificación determinista contra evidencia del ledger de Stellar.

No pretende ser simplemente otro explorador de bloques.

Un explorador responde:

> “¿Qué ocurrió en esta transacción?”

PROOF responde:

> “¿Lo que ocurrió respalda esta afirmación específica sobre el pago?”

Esta diferencia permite convertir la verificación en un servicio reutilizable y no solamente en una inspección manual.

#### Posibles vías de adopción

PROOF contempla dos modalidades complementarias:

**Verificación humana:** una persona proporciona una transacción y las condiciones que espera verificar.

**Verificación máquina a máquina:** la API HTTP y la interfaz MCP permiten que otros sistemas soliciten la misma adjudicación determinista.

Los posibles contextos incluyen plataformas de pago, marketplaces, comercio, conciliación, disputas, agentes y herramientas forenses.

Estos son **mercados y vías de integración potenciales**; todavía no constituyen demanda comercial demostrada.

---

### 3. Foco de producto

El recorrido principal responde una sola pregunta:

> **Me dijeron que este pago ocurrió. Verificalo.**

El usuario proporciona el hash de la transacción, la red Stellar y las propiedades del pago que quiera afirmar.

PROOF devuelve:

* **VERIFIED:** la evidencia disponible respalda todas las proposiciones requeridas.
* **NOT VERIFIED:** la evidencia fue obtenida, pero contradice al menos una proposición requerida.
* **INSUFFICIENT EVIDENCE:** no existe evidencia suficiente para afirmar o contradecir el claim de manera segura.

La última distinción es importante: **no poder verificar no equivale a verificar que algo no ocurrió.**

PROOF verifica hechos observables en el ledger. No transforma esos hechos en afirmaciones que el ledger no puede demostrar.

---

### 4. Ejecución técnica

PROOF implementa un pipeline verificable:

```text
Stellar
   ↓
adquisición
   ↓
evidencia estructurada
   ↓
PaymentClaim
   ↓
adjudicación determinista
   ↓
veredicto
   ↓
EvidenceBundle sellado
   ├── verificación independiente
   └── commitment Soroban
```

El motor determinista permanece separado de la adquisición externa y de la presentación.

Stellar cumple una función estructural: **es la fuente de la evidencia que PROOF evalúa**.

Soroban agrega una segunda propiedad: permite registrar on-chain un compromiso asociado a un resultado sellado. Ese compromiso aporta procedencia e integridad verificable; **no convierte al contrato en árbitro de la verdad del claim**.

Estado actual reportado:

* adjudicación determinista: **implementada**;
* bundles canónicos y sealing: **implementados**;
* verificador independiente: **implementado**;
* soporte multi-operación: **implementado**;
* disputas: **implementadas**;
* API HTTP: **implementada**;
* MCP: **implementado**;
* contrato Soroban: **desplegado y validado en Stellar Testnet**;
* red team: **realizado y findings tratados**;
* suite automatizada: **161 passed, 0 skipped**;
* deployment público: **desplegado en Google Cloud Run**;
* validación con usuarios: **pendiente**.

Evidencia reproducible en Testnet:

* Transacción de pago: `0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669`
* Ledger de pago: `4821215`
* Veredicto PROOF: `VERIFIED`
* Seal de evidencia: `c6d21734805d59886bc9a629893eb108a0666c74a03ed6e19e5abdc50e1b7d51`
* Contrato Soroban: `CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I`
* Ledger de commitment: `4821217`
* Ledger de receipt: `4821218`

El bundle sellado fue verificado independientemente, el tampering fue detectado
tras la mutación, y el commitment y receipt on-chain fueron recuperados del
contrato Soroban desplegado.

---
