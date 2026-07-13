# 🎯 oracle-hunter

Caçador automático de **vaga ARM grátis** na Oracle Cloud (Always Free · `VM.Standard.A1.Flex`).

A Oracle vive **sem capacidade ARM** em São Paulo ("Out of host capacity"). Este repositório fica
tentando criar a VM **a cada 15 minutos**, direto na infraestrutura do GitHub — então **nenhum
computador precisa ficar ligado**. Quando a vaga abrir, ele **cria a VM e abre uma Issue** avisando.

## Como funciona
- **`hunter.py`** — a cada rodada tenta **8 combinações**: 2 tamanhos (2 OCPU/12 GB e 1 OCPU/6 GB)
  × 4 domínios de falha (auto, FD-1, FD-2, FD-3). Vaga costuma abrir em domínios específicos.
- **`.github/workflows/hunt.yml`** — agenda de 15 em 15 min (≈770 tentativas/dia) e abre a Issue no sucesso.
- É **idempotente**: se a VM já existir, não cria outra.

## Segurança
**Nenhum segredo mora neste repositório.** As credenciais vêm de **GitHub Secrets** (criptografados —
não são expostos nem em repositório público, e não vazam para workflows de forks).

| Secret | O que é |
|---|---|
| `OCI_KEY` | Conteúdo do `.pem` (chave privada da API) — **o único segredo de verdade** |
| `OCI_USER` · `OCI_TENANCY` · `OCI_FINGERPRINT` | Identificadores da conta |
| `OCI_SUBNET` · `OCI_AD` · `OCI_REGION` | Onde a VM deve nascer |

## Quando conseguir
1. Pegar o **IP público** (console Oracle → Compute → Instances → `lm-bi`)
2. Rodar o **QUICK DEPLOY** do `DEPLOY.md` no repo do BI
3. **Desativar o cron** deste workflow (a caça acabou 🎉)

---
_Parte do projeto de BI Comercial. O app hoje roda no Streamlit Community Cloud; a VM ARM (12 GB)
resolveria de vez o aperto de memória do plano grátis._
