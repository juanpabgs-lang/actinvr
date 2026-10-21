# Alterna · alta a distancia (demostración)

Un cliente en Ciudad de México abre cuenta a medianoche. A las nueve, en Madrid, hay una cola de expedientes hechos: cada comprobación, cada evidencia, el riesgo, el contrato. Una persona decide.

**SINTÉTICO.** No hay datos de personas reales. No uses este código con expedientes vivos.

## Entidad

La mesa de Madrid es **Alterna Inversiones y Valores, S.G.I.I.C., S.A.** (CNMV nº 282, NIF A42939678), antes Actinver Inversiones y Valores. Los contratos y el centro de cumplimiento usan ese nombre. La marca visible se puede cambiar (`ONB_TENANT=actinver`).

Norfront es una empresa de Delaware con su equipo en Madrid.

## Cómo arrancar

```bash
# Tesseract (spa) y, si quieres resúmenes del modelo, Ollama + ministral-3:3b
# El modelo se ancla a digest f04aa1c738f6. Si no está, el alta sigue con plantilla.

cd ~/Norfront/demos/actinver-onboarding   # o el raíz de este repo
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cd frontend && npm ci && cd ..
./scripts/dev.sh
```

- Cliente, mesa y cumplimiento: [http://127.0.0.1:5173](http://127.0.0.1:5173) (en un agente Cursor: icono de puertos → **5173**, o `http://localhost:5173` si el auto-forward ya está)
- API: [http://127.0.0.1:8013](http://127.0.0.1:8013)
- Ambos escuchan en `0.0.0.0` para que Cursor los reenvíe. No abras `8013` en el navegador: la web usa `/api` por el proxy.
- Vista servida con CSP estricta: `cd frontend && npm run demo`

La guardia de red del proceso solo deja hablar con el bucle local y con Ollama. Eso no sustituye el cortafuegos del anfitrión; ver [deploy/nftables-egress.conf](deploy/nftables-egress.conf).

## Guion de la demo (12 minutos)

1. **Inicio.** Relojes CDMX y Madrid. Estado: modelo anclado, salida bloqueada, cadena íntegra.
2. **Cliente.** Persona «Rodrigo Iván Morales Trejo». Aviso RGPD y de IA. Documentos de muestra: el pasaporte se lee al momento. Firma con código simulado (el código aparece en pantalla; [proveedor SMS: no hay]).
3. **Mesa.** El expediente nuevo aparece en la cola. Ana Reyes recomienda. Pablo Ortiz acepta (cuatro ojos). Si abres a Luis Alberto Ramos Delgado, la aceptación pide a Lucía Méndez (PEP, art. 14.5.b).
4. **Cumplimiento.** «Probar fuga». Verificar la cadena. Demostrar manipulación en una copia. Exportar el ZIP de inspección. Leer el cuestionario Finreg. La columna en blanco del cuadro DORA es para el otro proveedor.
5. **Plataforma.** Qué está en esta demo y qué es siguiente.

## Qué está hecho

- Comprobaciones deterministas: MRZ ICAO 9303, CURP, RFC, CLABE, IBAN, OCR local, calidad de imagen, cruce de nombre y domicilio.
- Pack `ES-PBC v2026.10` (incluye RD 813/2026) y `MiFID-ALTERNA v2026.02`, cada regla con cita.
- Listas locales sintéticas (formato UE, ONU, OFAC, UIF). Un candidato no se cierra sin fecha o nacionalidad.
- Contrato PDF de Alterna, anexos, evidencia OTP, página de aceptación solo tras la firma humana.
- Modelo local Ministral 3 3B (Apache 2.0) para el resumen y la ayuda. Temperatura 0, semilla 42. No decide.
- Cadena SHA-256, bóveda AES-256-GCM por cliente, crypto-shredding, retención 10/5 años.
- Paquete de inspección ZIP + Ed25519.

## Lo que no decimos (corchetes)

- Norfront no tiene SOC 2 ni ISO 27001. No hay prueba de penetración.
- [Contacto de guardia y SLA ante una inspección de la CNMV: por acordar.]
- [Importes de costes: tarifario de Alterna.]
- [Proveedor SMS: no hay.]
- [Transposición española de la Directiva (UE) 2023/2673: no publicada a 20 oct 2026.]
- [Vigencia actual de la lista de terceros países equivalentes: verificar ante SEPBLAC.]
- [Pesos del modelo de riesgo: ejemplo. Calibración: Alterna / Finreg.]
- [Contrato de encargado del tratamiento: por firmar.]

Wonderful anuncia despliegue en servidor propio. No decimos que no puedan. El cuadro DORA lista las preguntas que cualquier proveedor tiene que responder.

## Pruebas

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npm run typecheck && npm run build
```
