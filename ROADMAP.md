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

1. **Oleada estructural filtrada (`T01–T15` válidas)** para endurecer contratos, CI, fronteras internas, adquisición, onboarding, diagnosis y DX del Módulo 1.
2. **BL-005** — ampliar cobertura de tickers por diversidad real, subordinada a `BL-067` (`T09 — Factoría de onboarding`)

Objetivos de esta fase:

- mantener 100% de regresión en los tickers validados;
- seguir reduciendo manualidad residual fuera del core de extracción;
- ampliar cobertura funcional del pipeline sin degradar provenance;
- hacer que añadir un ticker o un campo nuevo siga siendo un cambio local y verificable.
- mantener el paralelismo mutante real como capacidad diferida hasta que exista criterio explícito de `parallel-ready` y un proceso operativo formal, en lugar de improvisarlo sobre `main`.

`BL-057` ya quedó cerrado como mejora conservadora del path de acquire: SOM ya no depende de `filings_sources` hardcodeados y el piloto LSE/AIM se resuelve con discovery automático de 3 documentos núcleo. Si aparece masa crítica LSE/AIM en el futuro, el siguiente paso ya no es arreglar Somero, sino decidir si compensa subir esto a infraestructura de mercado más amplia.

## Horizonte siguiente: infraestructura para servir Módulo 1

Cuando el Módulo 1 sea suficientemente estable y la operación diaria sea predecible, las siguientes oportunidades naturales son:

- persistencia más estructurada de outputs;
- API de lectura para datos y provenance;
- scheduler de refresco;
- artefactos de consumo más cómodos que JSON en disco;
- soporte de producto sobre el `source_map.json` ya pilotado para “click to source”.

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
