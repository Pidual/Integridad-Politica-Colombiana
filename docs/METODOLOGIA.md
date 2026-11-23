# Metodología

Integridad Política Colombiana califica a quienes ocupan cargos públicos con dos ideas:

1. **Comparación justa entre pares.** Cada persona se compara solo con quienes ocupan
   un cargo equivalente en condiciones parecidas. Un alcalde de un municipio pequeño con
   poco presupuesto no se mide contra el alcalde de una capital.
2. **Todo dato tiene fuente.** Cada número y cada hecho enlaza a un registro público,
   una decisión oficial o una investigación periodística identificable.

La unidad de análisis es **la persona en su cargo durante todo su mandato** (por ejemplo,
"Alcaldía de Medellín, 2020–2023"). No hay temporadas: los años con datos se combinan.

## 1. Dos tipos de nota

| Cargo | Nota principal | Qué mide |
|---|---|---|
| Alcaldes y gobernadores | **Desempeño del mandato** (1–10, 6,0 = promedio del grupo) | Gestión, finanzas, contratación y ciudadanía, con datos oficiales |
| Senadores | **Integridad** (1–10, base 8) | Hechos documentados en contra y a favor (bitácora de integridad) |

En el Senado, la actividad legislativa (proyectos, ponencias, debates) se muestra como
información, pero no cuenta en la nota.

## 2. Nota de desempeño (alcaldes y gobernadores)

**Grupos de comparación.** Los municipios se agrupan según los *grupos de capacidades*
del DNP (Ciudades, G1–G5), que el DNP creó precisamente para comparar municipios con
condiciones iniciales similares. Si falta ese dato se usa la categoría de la Ley 617
(Especial–1, 2–3, 4–6). Los departamentos forman un solo grupo. Un grupo con menos de
8 integrantes se compara con todo el cargo.

**Cálculo.**
1. Cada métrica se normaliza contra el grupo con un puntaje z robusto
   (`z = (x − mediana) / (1,4826 · MAD)`), con el signo invertido cuando menos es mejor
   (p. ej. % de contratación directa), y se limita a ±3 para que un valor atípico no domine.
2. Puntaje por categoría = promedio ponderado de sus métricas.
3. Puntaje global = promedio ponderado de las categorías (pesos en `scoring/config.json`).
4. Prudencia ante poca evidencia: `global · n / (n + 2)`, con `n` = métricas disponibles.
5. Escala: `nota = 6,0 + 1,5 · global`, entre 1 y 10.
6. **Cobertura mínima:** si hay datos para menos del 50 % del peso de las métricas, no se
   da nota global ("N/D"); las categorías con datos sí se muestran.

**Nivel y avance.** Las ciudades ricas puntúan alto en niveles (IDF, MDM) casi por
defecto. Para premiar la gestión y no el presupuesto, también se mide el **cambio durante
el mandato** (`mdm_delta` y, cuando haya datos, homicidios y Saber 11).

**Mandato completo.** Los años de un mismo mandato se combinan: promedio de cada métrica,
último año para los cambios (avance acumulado) y suma de volúmenes de SECOP.

## 3. Nota de integridad (senadores)

Cada persona parte de **8,0** ("sin hallazgos registrados, ni a favor ni en contra") y la
nota se mueve con cada hecho documentado en la bitácora (`data/eventos/eventos.json`):

| En contra | Ejemplos | Resta |
|---|---|---|
| **N1 · Decisión en firme** | Condena ejecutoriada, destitución o inhabilidad, fallo de responsabilidad fiscal, pérdida de investidura | −4 |
| Condena no en firme | Sentencia de primera instancia apelable | −3 |
| **N2 · Proceso formal abierto** | Investigación formal o indagatoria en la Corte Suprema, imputación o acusación, pliego de cargos | −2 |
| **N3 · Indagación preliminar o investigación periodística documentada** | Indagación previa; investigación de un medio con documentos | −1,5 |
| Archivado, absuelto, revocado, desmentido | — | 0 (se muestra) |

| A favor | Ejemplos | Suma |
|---|---|---|
| **P1 · Transparencia verificable** | Publica completa su declaración de bienes, renta y conflictos de interés (Ley 2013), su agenda o la contratación de su UTL | +0,5 |
| **P2 · Denuncia con resultado oficial** | Su denuncia llevó a una investigación, imputación o sanción verificable | +1,0 |
| **P3 · Reconocimiento independiente** | Premio o ranking con metodología pública (p. ej. Panel de Opinión de Cifras y Conceptos) | +0,75 |

Los aportes a favor suman como máximo +2; la nota va de 1 a 10. Un 10 no se obtiene por
ausencia de hallazgos: hay que demostrar transparencia.

**Reglas de la bitácora.**
- Un evento por hecho, redactado en lenguaje neutral, con al menos una fuente enlazada.
- Se registran el estado procesal, las rectificaciones y la respuesta de la persona.
- Lo que solo involucra a familiares no se le atribuye.
- **Presunción de inocencia:** un proceso abierto no es una condena, y así se indica.
- **Revisión editorial obligatoria:** solo se publican eventos aprobados por una persona
  del equipo (`python data/eventos/revisar.py --aprobar ID --por "Nombre"`).
- **Derecho de rectificación:** cada expediente tiene un enlace para solicitar correcciones.

## 4. Fuentes

| Fuente | Qué aporta |
|---|---|
| DNP: MDM, MDD, IDF | Desempeño municipal y departamental, desempeño fiscal, grupos de capacidades |
| SECOP I y II (Colombia Compra Eficiente) | Contratación directa, procesos con oferente único, prórrogas |
| Contaduría (CHIP) y DANE (DIVIPOLA) | Identificación de entidades: código y NIT |
| Registraduría | Mandatarios elegidos |
| Senado: directorio, Sección de Leyes, Secretaría General; Gaceta del Congreso | Listado y fotos oficiales, proyectos, ponencias, proposiciones, actas |
| Corte Suprema, Procuraduría, Contraloría, Consejo de Estado (vía comunicados y prensa) | Procesos y decisiones de la bitácora |
| Prensa e investigación periodística | Hechos documentados, siempre con enlace |
| Wikipedia | Perfil biográfico (fuente secundaria, solo contexto) |

Detalle técnico de cada conector en `docs/DATOS.md`.

## 5. Pendientes

1. Índices del DNP de 2022 en adelante para calificar a los mandatarios 2024–2027.
2. Homicidios (Policía), Saber 11 (ICFES) y vacunación (MinSalud) por API.
3. Cumplimiento de la Ley 2013 por persona (P1 automático).
4. Financiadores de campaña que reciben contratos (CNE Cuentas Claras × SECOP).
5. Asistencia y votaciones del Senado a partir de las actas de la Gaceta.
6. Cámara de Representantes.
