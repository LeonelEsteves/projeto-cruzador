-- Consulta isolada para inspecionar AKC010 e CT5010 lado a lado,
-- usando AKD010 e CT2010 como ponte de contexto.
--
-- Relacoes usadas:
--   AKC.AKC_PROCES = AKD.AKD_PROCES
--   AKC.AKC_ITEM   = AKD.AKD_ITEM
--   AKC.AKC_SEQ    = AKD.AKD_SEQ
--
--   CT5.CT5_LANPAD = CT2.CT2_LP
--   CT5.CT5_SEQUEN = CT2.CT2_SEQLAN
--
-- Associacao AKD x CT2 usada nesta consulta:
--   1) AKD_XDOC   = CT2_XDOC
--   2) AKD_XDOC   = CT2_AT01CR
--   3) AKD_XNUMAP = CT2_XDOCUM
--   4) AKD_XNUMAP = CT2_AT04DB
--
-- Ajuste os filtros finais conforme necessario:
--   :p_proces   -> filtra processo AKD/AKC
--   :p_lp       -> filtra LP da CT2/CT5
--   :p_akd_recno
--   :p_ct2_recno

WITH pares_base AS (
    SELECT
        akd.R_E_C_N_O_ AS akd_recno,
        ct2.R_E_C_N_O_ AS ct2_recno,
        TRIM(akd.AKD_FILIAL) AS akd_filial,
        TRIM(akd.AKD_PROCES) AS akd_proces,
        TRIM(akd.AKD_ITEM) AS akd_item,
        TRIM(akd.AKD_SEQ) AS akd_seq,
        TRIM(akd.AKD_DATA) AS akd_data,
        akd.AKD_VALOR1 AS akd_valor1,
        TRIM(akd.AKD_HIST) AS akd_hist,
        TRIM(akd.AKD_XDOC) AS akd_xdoc,
        TRIM(akd.AKD_XNUMAP) AS akd_xnumap,
        TRIM(ct2.CT2_FILIAL) AS ct2_filial,
        TRIM(ct2.CT2_DATA) AS ct2_data,
        ct2.CT2_VALOR AS ct2_valor,
        TRIM(ct2.CT2_HIST) AS ct2_hist,
        TRIM(ct2.CT2_LP) AS ct2_lp,
        TRIM(ct2.CT2_SEQLAN) AS ct2_seqlan,
        TRIM(ct2.CT2_XDOC) AS ct2_xdoc,
        TRIM(ct2.CT2_AT01CR) AS ct2_at01cr,
        TRIM(ct2.CT2_XDOCUM) AS ct2_xdocum,
        TRIM(ct2.CT2_AT04DB) AS ct2_at04db
    FROM PROTHEUS_APEX.AKD010 akd
    JOIN PROTHEUS_APEX.CT2010 ct2
      ON (
            (TRIM(akd.AKD_XDOC) IS NOT NULL AND TRIM(akd.AKD_XDOC) = TRIM(ct2.CT2_XDOC))
         OR (TRIM(akd.AKD_XDOC) IS NOT NULL AND TRIM(akd.AKD_XDOC) = TRIM(ct2.CT2_AT01CR))
         OR (TRIM(akd.AKD_XNUMAP) IS NOT NULL AND TRIM(akd.AKD_XNUMAP) = TRIM(ct2.CT2_XDOCUM))
         OR (TRIM(akd.AKD_XNUMAP) IS NOT NULL AND TRIM(akd.AKD_XNUMAP) = TRIM(ct2.CT2_AT04DB))
      )
    WHERE akd.D_E_L_E_T_ = ' '
      AND ct2.D_E_L_E_T_ = ' '
      AND TRIM(akd.AKD_TPSALD) IN ('LQ', 'PG', 'AR', 'RB')
      AND TRIM(ct2.CT2_MOEDLC) = '01'
      AND TRIM(ct2.CT2_DC) IN ('1', '2')
)
SELECT
    pb.akd_recno,
    pb.ct2_recno,
    pb.akd_filial,
    pb.ct2_filial,
    pb.akd_proces,
    pb.akd_item,
    pb.akd_seq,
    pb.ct2_lp,
    pb.ct2_seqlan,
    pb.akd_data,
    pb.ct2_data,
    pb.akd_valor1,
    pb.ct2_valor,
    pb.akd_xdoc,
    pb.ct2_xdoc,
    pb.ct2_at01cr,
    pb.akd_xnumap,
    pb.ct2_xdocum,
    pb.ct2_at04db,
    pb.akd_hist,
    pb.ct2_hist,
    akc.AKC_PROCES,
    akc.AKC_ITEM,
    akc.AKC_SEQ,
    akc.AKC_XDOC,
    ct5.CT5_LANPAD,
    ct5.CT5_SEQUEN,
    ct5.CT5_ORIGEM,
    ct5.CT5_DESC,
    ct5.CT5_XDOC
FROM pares_base pb
LEFT JOIN PROTHEUS_APEX.AKC010 akc
       ON TRIM(akc.AKC_PROCES) = pb.akd_proces
      AND TRIM(akc.AKC_ITEM) = pb.akd_item
      AND TRIM(akc.AKC_SEQ) = pb.akd_seq
LEFT JOIN PROTHEUS_APEX.CT5010 ct5
       ON TRIM(ct5.CT5_LANPAD) = pb.ct2_lp
      AND TRIM(ct5.CT5_SEQUEN) = pb.ct2_seqlan
WHERE (:p_proces IS NULL OR pb.akd_proces = :p_proces)
  AND (:p_lp IS NULL OR pb.ct2_lp = :p_lp)
  AND (:p_akd_recno IS NULL OR pb.akd_recno = :p_akd_recno)
  AND (:p_ct2_recno IS NULL OR pb.ct2_recno = :p_ct2_recno)
ORDER BY
    pb.akd_proces,
    pb.ct2_lp,
    pb.akd_item,
    pb.akd_seq,
    pb.ct2_seqlan,
    pb.akd_recno,
    pb.ct2_recno;
