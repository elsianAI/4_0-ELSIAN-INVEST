# ELSIAN-INVEST 4.0 — Roadmap

> Horizonte de producto y tecnología para ELSIAN 4.0.
> No describe el estado vivo del repo; para eso manda `docs/project/PROJECT_STATE.md`.

## Principio rector

ELSIAN 4.0 avanza por capas, pero el orden no es negociable:

1. consolidar el **Módulo 1** determinista;
2. cerrar la autonomía suficiente de extracción y adquisición donde sea razonable;
3. ampliar cobertura y campos;
4. solo después abrir infraestructura de producto y módulos superiores.

## Horizonte inmediato: cerrar Módulo 1 de forma sostenible

Trabajo prioritario una vez el repo esté limpio y sincronizado:

1. **BL-052** — auto-curate para tickers no-SEC
2. **BL-053** — Provenance Level 3
3. **BL-057** — discovery automático de filings LSE/AIM

Objetivos de esta fase:

- mantener 100% de regresión en los tickers validados;
- seguir reduciendo manualidad residual fuera del core de extracción;
- ampliar cobertura funcional del pipeline sin degradar provenance;
- hacer que añadir un ticker o un campo nuevo siga siendo un cambio local y verificable.

La mejora `BL-057` (auto-discovery LSE/AIM) sigue existiendo, pero vuelve a una postura conservadora: no bloquea el avance inmediato y solo debe subir de prioridad si aparece masa crítica LSE/AIM o un trigger claro de adquisición no-SEC.

## Horizonte siguiente: infraestructura para servir Módulo 1

Cuando el Módulo 1 sea suficientemente estable y la operación diaria sea predecible, las siguientes oportunidades naturales son:

- persistencia más estructurada de outputs;
- API de lectura para datos y provenance;
- scheduler de refresco;
- artefactos de consumo más cómodos que JSON en disco;
- soporte técnico de “click to source” sobre provenance Level 3.

Esto sigue siendo infraestructura de producto, no un cambio de foco. No debe competir con el backlog activo mientras el Módulo 1 siga cerrando gaps de extracción/adquisición.

## Módulos futuros (deferidos)

### Módulo 2 — Extracción cualitativa

Procesar MD&A, risk factors, guidance y cambios narrativos con trazabilidad al párrafo fuente.

### Módulo 3 — Fallback LLM cuantitativo

Completar o revisar casos donde el pipeline determinista no pueda extraer un dato con confianza suficiente. Siempre marcado como asistencia, nunca como sustituto silencioso del pipeline determinista.

### Módulo 4 — Análisis y decisión

Consumir truth packs y métricas derivadas para evaluación de negocio, narrativa y decisión.

## Lo que este roadmap no hace

- No fija fechas cerradas.
- No promete un “producto comercial” ya listo.
- No presenta módulos 2/3/4 como trabajo operativo inmediato.
- No sustituye a `VISION.md` ni a `PROJECT_STATE.md`.

## Regla de avance

Una iniciativa futura solo pasa de oportunidad a backlog activo cuando:

- tiene un trigger real;
- no compite con una deuda crítica del Módulo 1;
- existe alcance concreto y criterio de salida verificable.
