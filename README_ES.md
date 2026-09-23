# PROOF

[Español](README_ES.md) | **English** | [Technical README](TECHNICAL.md)

## El problema

Alguien te manda una captura diciendo que te pagó. La mirás. Parece real.
Pero no podés saberlo — una captura es una imagen, no evidencia. Se puede
editar, fabricar, o sacar de una transacción distinta.

La pregunta no es "¿esta captura parece real?" La pregunta es:
**¿este pago realmente ocurrió en el ledger de Stellar?**

## Qué hace PROOF

PROOF recibe un hash de transacción de Stellar y un payment claim,
reconstruye los hechos desde el ledger, y produce un evidence bundle sellado
con un veredicto.

```
"Alice le pagó a Bob 100 USDC por la factura INV-184"
                    |
                    v
           Stellar ledger (hash de transacción)
                    |
                    v
          Extracción determinista de evidencia
                    |
                    v
          Adjudicación: claim vs evidencia
                    |
                    v
          VERIFIED / NOT VERIFIED / INSUFFICIENT EVIDENCE
                    |
                    v
          Evidence bundle sellado (SHA-256)
```

PROOF no mira capturas. Mira el ledger.

## Comportamiento observable

**Claim: "100 USDC de Alice a Bob por INV-184"**

```
EVIDENCE
  transacción existe          PASS
  transacción exitosa         PASS
  emisor coincide              PASS
  receptor coincide            PASS
  asset coincide               PASS
  monto = 100 USDC             PASS
  referencia = INV-184         PASS

VEREDICTO: VERIFIED
Seal: sha256:...
```

**Claim: "100 USDC a Bob" (pero la transacción fue a otro lado)**

```
EVIDENCE
  transacción existe          PASS
  transacción exitosa         PASS
  monto = 100 USDC             PASS
  receptor coincide            FAIL  (esperado Bob, recibido otro)

VEREDICTO: NOT VERIFIED
```

**Claim: "100 USDC pagados, mercadería entregada"**

```
EVIDENCE
  transacción existe          PASS
  transacción exitosa         PASS
  monto = 100 USDC             PASS

VEREDICTO: VERIFIED
ENTREGA: FUERA DEL ALCANCE DE LA EVIDENCIA
```

PROOF verifica lo que el ledger puede probar. No afirma más que eso.

## Lo que PROOF no prueba

Estas no son limitaciones para esconder — son los límites que hacen que el
veredicto sea confiable:

- **Pago ejecutado no es deuda saldada.** Una transacción exitosa prueba
  que el activo se movió. No prueba que la obligación subyacente esté
  legalmente cumplida.
- **Transacción existe no es mercadería entregada.** El ledger registra
  eventos financieros, no físicos.
- **Wallet firmó no es identidad humana.** Una firma prueba que se usó
  una clave, no quién estaba detrás del teclado.

## Cómo funciona

1. **Entrada:** un `PaymentClaim` (hash de transacción + aserciones
   opcionales: emisor, receptor, asset, monto, referencia, ventana de
   ledger) y una red (testnet o mainnet).
2. **Fetch:** PROOF consulta la API de Stellar Horizon por la transacción
   y sus operaciones.
3. **Extracción:** se reconstruyen los hechos relevantes del pago: emisor,
   receptor, asset, monto (en stroops enteros), timestamp, estado de
   éxito, memo.
4. **Adjudicación:** cada proposición del claim se chequea
   independientemente contra la evidencia. Campos no especificados son
   ABSTAIN, no asumidos verdaderos.
5. **Sellado:** el claim, la evidencia, los checks y el veredicto se
   canonicalizan (tipados, ordenados, versionados) y se sellan con SHA-256.
6. **Verificación:** un verificador independiente (solo stdlib) puede
   recalcular el seal y confirmar que el bundle no fue alterado.

## Repositorio

```
proof/
  canonicalize.py    # serialización tipada, ordenada, versionada + seal SHA-256
  claim.py           # PaymentClaim — lo que alguien afirma que ocurrió
  evidence.py        # PaymentEvidence, CheckResult, EvidenceBundle
  stellar_client.py  # wrapper de la API de Horizon (testnet + mainnet)
  extractor.py       # reconstruir evidencia desde tx + operaciones
  adjudicator.py     # comparar claim vs evidencia, producir checks + veredicto
  verifier.py        # verificador independiente de bundles (solo stdlib)
  engine.py          # entry point: verify_payment(claim, network)
tests/               # 55 tests: canonicalización, adjudicación, determinismo, boundary
```

## Probalo

```bash
cd proof
source .venv/bin/activate

python -c "
from proof import PaymentClaim, verify_payment

claim = PaymentClaim(
    transaction_hash='tu_hash_aqui',
)
bundle = verify_payment(claim, network='testnet')
print(bundle.verdict)
print(bundle.seal)
"
```

## Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

55 tests cubriendo: serialización canónica, validación de claims,
lógica de adjudicación, detección de alteraciones, y determinismo.

Para la arquitectura completa, modelo de amenazas, y decisiones de diseño,
ver el [Technical README](TECHNICAL.md).
