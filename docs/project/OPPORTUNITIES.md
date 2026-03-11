# ELSIAN-INVEST 4.0 — Opportunities

> Carril para ideas de medio/largo plazo y trabajo no ejecutable todavía.
> Si una idea adquiere alcance claro, criterio de salida y prioridad operativa, se convierte en una BL y pasa a `docs/project/BACKLOG.md`.

---

## Reglas de uso

- Este fichero no compite con el backlog operativo.
- No usar estados formales. Agrupar por tema y mantener notas breves.
- Si una oportunidad depende de que Módulo 1 alcance más madurez, decirlo explícitamente.
- Si una oportunidad sale de una decisión estratégica, enlazar la `DEC-*` correspondiente.

---

## Producto y distribución

- API de datos para servir outputs del Módulo 1 con provenance utilizable.
- Visor web con “click to source” apoyado en provenance L3.
- Scheduler / refresh continuo de tickers validados.
- Packaging de outputs para consumo externo más allá de JSON en disco.

## Módulos futuros

- Módulo 2: extracción cualitativa (MD&A, risk factors, guidance) con trazabilidad al párrafo.
- Módulo 3: fallback LLM cuantitativo para casos donde la capa determinista no pueda recuperar el dato.
- Módulo 4: análisis y decisión sobre truth packs y métricas derivadas.

## Calidad y operación

- Informes de salud de repo periódicos cuando el briefing manual deje de ser suficiente.
- Más tests de patrón reutilizable, no solo por ticker.
- Endurecimiento adicional de CI cuando el coste de ejecución sea estable y asumible.
- Detección más rica de drift documental o operativo si aparece fricción real en el uso diario.

## Operación y releases

- Lane de experimentos y releases para desacoplar pruebas, validación y promoción a runtime estable sin contaminar el backlog ejecutable de Module 1.

## Cobertura y fuentes

- Más tickers solo cuando cubran gaps reales de mercado, regulador o formato.
- Nuevas rutas de adquisición no-SEC cuando exista masa crítica suficiente para justificar el coste.
- Mejor cobertura de mercados europeos, Asia y sectores no representados.

## Frontera Module 1

- `SOM` queda en frontera abierta: ticker validado `ANNUAL_ONLY`, pero sin evidencia canónica suficiente todavía para cerrarlo como `ANNUAL_ONLY justificado` ni para empaquetar una promoción como BL-ready.
- Generalizar HKEX más allá de `0327` no es backlog vivo hoy. El cierre actual valida un ticker `FULL` con `hkex_manual` reproducible desde git, no un programa de mercado autónomo.
- LSE/AIM más allá del piloto `SOM` sigue fuera del backlog operativo. `BL-057` resuelve un piloto conservador de un ticker; no hay masa crítica suficiente para declarar capacidad de mercado amplia.
- Euronext no-API más allá de `TEP` sigue siendo carril de oportunidad. El ticker actual opera por excepción documentada; no hay packet BL-ready para convertir eso en capacidad de mercado general.
- El gap factual de coverage/manifest de `TALO` no se empaqueta todavía como BL: los canonicals lo tratan como limitación conocida del runtime actual, no como bug ya diagnosticado con aceptación técnica cerrada.
- Los 4 gaps residuales de field dependency (`fx_effect_cash`, `other_cash_adjustments`, `market_cap`, `price`) siguen fuera del backlog vivo mientras no pasen de oportunidad a necesidad operativa clara.

## Nota

- Mantener estas ideas fuera del flujo activo evita mezclar visión de producto con ejecución del Módulo 1.
