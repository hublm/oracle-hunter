# -*- coding: utf-8 -*-
"""Caçador de vaga ARM na Oracle Cloud (Always Free · VM.Standard.A1.Flex).

Roda no GitHub Actions (agendado). **NÃO guarda segredo nenhum**: as credenciais vêm
de variáveis de ambiente (GitHub Secrets, criptografados — não aparecem nem em repo público).

A cada execução testa 8 combinações: 2 tamanhos (2 OCPU/12GB e 1 OCPU/6GB) × 4 domínios de
falha (auto, FD-1, FD-2, FD-3). Vagas costumam aparecer em domínios específicos.

Saída:
  0  → conseguiu (ou a VM já existe) · grava o OCID em vm.txt → o workflow abre uma Issue
  75 → sem vaga nesta rodada (normal, não é erro)
"""
import os
import sys
import time

import oci

# saída em UTF-8 (o console do Windows é cp1252 e quebra com acento/emoji; no Actions é Linux/UTF-8)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---- credenciais (GitHub Secrets) ------------------------------------------------------ #
CFG = {
    "user": os.environ["OCI_USER"],
    "fingerprint": os.environ["OCI_FINGERPRINT"],
    "tenancy": os.environ["OCI_TENANCY"],
    "region": os.environ.get("OCI_REGION", "sa-saopaulo-1"),
    "key_content": os.environ["OCI_KEY"],          # conteúdo do .pem (não o caminho)
}
SUBNET = os.environ["OCI_SUBNET"]
AD = os.environ.get("OCI_AD", "qqxB:SA-SAOPAULO-1-AD-1")

# ---- infra (não é segredo: imagem pública da Oracle e chave SSH PÚBLICA) ---------------- #
IMAGE = os.environ.get(
    "OCI_IMAGE",
    "ocid1.image.oc1.sa-saopaulo-1.aaaaaaaaemf52b7af7ncncxz6pdc6hrlkdmylvwejfzpwnpbuhlfxwhrno6a")
SSH_PUB = os.environ.get(
    "SSH_PUB",
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINXJpcR4Xy2wvYdGoexFL8cZdx2QFewkBis9iTtgFFAk lm-bi-deploy")

NAME = "lm-bi"
BOOT_GB = 50
SHAPES = [(2, 12), (1, 6)]                                   # tenta a maior primeiro
FDS = [None, "FAULT-DOMAIN-1", "FAULT-DOMAIN-2", "FAULT-DOMAIN-3"]

compute = oci.core.ComputeClient(CFG)


def salvar(ocid):
    with open("vm.txt", "w", encoding="utf-8") as f:
        f.write(ocid)


def detalhes(ocpus, mem, fd):
    d = oci.core.models.LaunchInstanceDetails(
        availability_domain=AD, compartment_id=CFG["tenancy"], display_name=NAME,
        shape="VM.Standard.A1.Flex",
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=ocpus, memory_in_gbs=mem),
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            image_id=IMAGE, boot_volume_size_in_gbs=BOOT_GB),
        create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=SUBNET, assign_public_ip=True),
        metadata={"ssh_authorized_keys": SSH_PUB})
    if fd:
        d.fault_domain = fd
    return d


# ---- se a VM já existe, não faz nada (idempotente) -------------------------------------- #
try:
    for i in compute.list_instances(CFG["tenancy"]).data:
        if i.display_name == NAME and i.lifecycle_state in ("RUNNING", "PROVISIONING", "STARTING"):
            print(f"✅ A VM JÁ EXISTE: {i.id}  ({i.lifecycle_state})")
            salvar(i.id)
            sys.exit(0)
except Exception as e:
    print(f"(aviso) não consegui listar instâncias: {type(e).__name__}: {e}")

# ---- caça: VÁRIAS rodadas dentro da janela ---------------------------------------------- #
# POR QUE UM LOOP LONGO: o cron do GitHub é despriorizado/descartado sob carga — configuramos
# 15 min e na prática ele dispara poucas vezes por dia. Então cada disparo tem que VALER MAIS:
# em vez de 8 tentativas e sair, ficamos ~6 min tentando (≈60 tentativas por disparo).
MINUTOS = float(os.environ.get("MINUTOS", "6"))
FIM = time.time() + MINUTOS * 60

rodada = 0
total = 0
while time.time() < FIM:
    rodada += 1
    print(f"\n── rodada {rodada} ─────────────────────────")
    for ocpus, mem in SHAPES:
        for fd in FDS:
            if time.time() >= FIM:
                break
            total += 1
            alvo = f"{ocpus}OCPU/{mem}GB · fd={fd or 'auto'}"
            try:
                r = compute.launch_instance(detalhes(ocpus, mem, fd))
                print(f"\n🎉 *** VM CRIADA! *** ({alvo})\n    OCID: {r.data.id}")
                salvar(r.data.id)
                sys.exit(0)
            except oci.exceptions.ServiceError as e:
                msg = (e.message or "").lower()
                if "capacity" in msg or "out of host" in msg or e.status in (429, 500):
                    print(f"  {alvo}: sem capacidade")
                elif "fault domain" in msg or "invalid" in msg:
                    print(f"  {alvo}: domínio inválido — pulando")
                else:
                    print(f"  {alvo}: ERRO {e.status} {e.code} — {e.message}")
                    if e.status in (401, 403, 404):   # credencial/permissão: insistir não adianta
                        sys.exit(1)
            except Exception as e:
                print(f"  {alvo}: falha de conexão ({type(e).__name__})")
            time.sleep(3)
    time.sleep(5)   # respiro entre rodadas (não é rajada)

print(f"\nSem vaga: {total} tentativas em {MINUTOS:.0f} min ({rodada} rodadas). "
      f"A caça continua no próximo agendamento.")
sys.exit(75)
