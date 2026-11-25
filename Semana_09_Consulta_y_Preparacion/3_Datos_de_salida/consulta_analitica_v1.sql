SELECT
  e.evaluacion_id,
  e.fecha,
  m.modulo,
  t.turno,
  e.valvula,
  e.plantas_evaluadas,
  e.aranita_hojas_infestadas     AS hojas_inf_pct,
  e.aranita_infestacion_postura  AS postura_pct,
  c.temperatura_oc,
  c.humedad_relativa,
  c.estado_calidad_clima
FROM evaluacion_fitosanitaria e
JOIN clima_diario c ON c.fecha     = e.fecha
JOIN dim_modulo   m ON m.modulo_id = e.modulo_id
JOIN dim_turno    t ON t.turno_id  = e.turno_id
WHERE e.estado_calidad_evaluacion = 'ACEPTADO'
  AND e.fecha BETWEEN '2026-03-01' AND '2026-08-31'
ORDER BY e.fecha, m.modulo, e.valvula, t.turno;
