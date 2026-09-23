# CONTRIBUIR A PROOF

**Repositorio:** `https://github.com/annatchijova/proof`
**Autora:** Anna Tchijova
**Última actualización:** Septiembre 2026

> This guide is also available in English: [`CONTRIBUTING.md`](CONTRIBUTING.md)

---

## Nota de la autora

PROOF no es perfecto, y lo sé.

Esto no es un disclaimer. Es un principio de diseño. Un sistema de
verificación que no puede documentar sus propios modos de fallo es
no confiable por definición. El mismo estándar epistemológico que
aplico a la evidencia, lo aplico a este código.

Si encontrás algo mal — un bug, un caso donde el veredicto es
incorrecto, una falla de determinismo, un gap de cobertura — quiero
saberlo. No me voy a poner a la defensiva. La crítica no es un ataque
al proyecto. La crítica *es* el proyecto funcionando como debe.

Por favor, sé directo.

---

## Congelamiento de protocolo

El protocolo de PROOF y el contrato Soroban están **congelados** desde
v0.1.0. Los siguientes componentes están congelados y no cambiarán
salvo para corregir un bug confirmado:

- Contrato Soroban `proof-registry` v0.1.0
- Hash de commitment: `SHA-256(canonical(CommitmentTerms))`, versión 1
- Schema del evidence bundle versión 1
- Veredictos: `VERIFIED`, `NOT_VERIFIED`, `INSUFFICIENT_EVIDENCE`
- Estados de check: `PASS`, `FAIL`, `ABSTAIN`
- Surface del API público y modelo de autorización
- Herramientas MCP

**Lo que se permite después del freeze:**

- Bug fixes confirmados por evidencia
- Tests
- Wiring de deployment
- Pulido de UI/demo
- Documentación
- Validación de producto

**Lo que no se permite:**

- Nuevas capabilities
- Cambios de protocolo/schema/semántica
- Shortcuts de escritura pública
- Agregar una identidad fondeada solo para hacer la demo más vistosa

Si tu contribución requiere un cambio de protocolo o schema, abrí un
issue primero para discutir si califica como bug fix o si requiere un
protocolo v2.

---

## Lo que PROOF no cubre

PROOF verifica hechos verificables del ledger: existencia de
transacción, éxito, sender, recipient, asset, amount, ledger, rango
de tiempo, y memo. No verifica:

- Que los bienes o servicios fueron entregados
- Que una deuda fue legalmente satisfecha
- Que la persona que controla un wallet es un humano específico
- Que los términos commiteados son verdaderos (solo que fueron commiteados)

Si contribuís una feature que claims verificar algo de lo anterior, no
se va a mergear. Esto está fuera de scope por diseño, no por
descuido.

---

## Cómo contribuir

### Reportar issues

Abrí un issue en GitHub. Incluí:

- Versión de PROOF o commit hash
- El input específico (transaction hash, campos del claim) que
  triggera el issue
- Output observado vs. output esperado
- Si es un issue de correctitud (veredicto incorrecto), de determinismo
  (output inconsistente en input idéntico), o de usabilidad

Para vulnerabilidades de seguridad, leé [`SECURITY.md`](SECURITY.md)
primero. No abras issues públicos para bugs de seguridad.

### Contribuciones de código

1. Forkeá el repositorio
2. Creá una branch con un nombre descriptivo
3. Corré la suite completa antes de subir: `pytest tests/ -v`
4. Cero regresiones son aceptables. Si tu patch introduce una
   regresión, explicá por qué en la descripción del PR y cuál es el
   tradeoff
5. Todo código nuevo que toque el decision path del veredicto debe
   incluir un test de determinismo — input idéntico debe producir
   output idéntico
6. Si tu contribución modifica la lógica de veredicto, incluí una
   actualización correspondiente de `TECHNICAL.md` si resuelve una
   limitación documentada, o una entrada nueva si introduce una
7. Nada de float en el decision path. Usá `fractions.Fraction` o
   enteros. Floats solo en la capa de display, nunca en un valor que
   se selle
8. El LLM (si lo hay) no debe influir en ningún valor sellado. El
   engine determinístico produce y sella el resultado antes de que
   corra cualquier capa narrativa

### Contribuciones de tests

Los nuevos casos de test deben seguir la estructura existente en
`tests/`. Cada test debe discriminar, no solo ejecutar. Un test que
corre un check sin pinear su boundary exacta no verifica nada.

Para tests de integración contra transacciones reales de Testnet, usá
la transacción reproducible documentada en `README.md`:

- Payment tx: `0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669`
- Payment ledger: `4821215`
- Veredicto esperado: `VERIFIED`
- Evidence seal: `c6d21734805d59886bc9a629893eb108a0666c74a03ed6e19e5abdc50e1b7d51`

No envíes tests que "rompan" el sistema y luego clasifiquen eso como
déficits de accuracy. Leé el framing de accuracy en el red-team review
antes de abrir issues sobre conteos de veredictos.

### Contribuciones de documentación

El código contiene documentación en inglés. Traducciones al español
son bienvenidas. Mantené precisión técnica — no simplifiques
terminología para hacer la traducción más fácil.

---

## Lo que no voy a mergear

- Cualquier cosa que introduzca operaciones de float en el decision
  path del veredicto sin justificación documentada y proof de
  determinismo
- Cualquier cosa que permita a un LLM influir en veredictos, seals, o
  cualquier valor sellado
- Cualquier cosa que agregue un shortcut de escritura pública al
  deployment sin preservar el modelo de autorización congelado
- Cualquier cosa que claims que PROOF verifica satisfacción legal,
  entrega de bienes, o identidad humana
- Patches que "arreglen" veredictos de INSUFFICIENT_EVIDENCE en casos
  epistémicamente ambiguos forzando un VERIFIED o NOT_VERIFIED
- Nuevas capabilities de protocolo o cambios de schema (post-freeze)

---

## Licencia

Todas las contribuciones se aceptan bajo la licencia Apache 2.0 del
proyecto. Al enviar un pull request, confirmás que tenés el derecho de
licenciar tu contribución bajo estos términos.

---

*"Un sistema de verificación que no puede ser falsificado no puede ser confiable."*

*— Anna Tchijova, Proyecto PROOF*
