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

# ---- rodada de tentativas (2 shapes × 4 domínios) --------------------------------------- #
n = 0
for ocpus, mem in SHAPES:
    for fd in FDS:
        n += 1
        alvo = f"{ocpus}OCPU/{mem}GB · fd={fd or 'auto'}"
        try:
            r = compute.launch_instance(detalhes(ocpus, mem, fd))
            print(f"\n🎉 *** VM CRIADA! *** ({alvo})\n    OCID: {r.data.id}")
            salvar(r.data.id)
            sys.exit(0)
        except oci.exceptions.ServiceError as e:
            msg = (e.message or "").lower()
            if "capacity" in msg or "out of host" in msg or e.status in (429, 500):
                print(f"  [{n}/8] {alvo}: sem capacidade")
            elif "fault domain" in msg or "invalid" in msg:
                print(f"  [{n}/8] {alvo}: domínio inválido — pulando")
            else:
                print(f"  [{n}/8] {alvo}: ERRO {e.status} {e.code} — {e.message}")
        except Exception as e:
            print(f"  [{n}/8] {alvo}: falha de conexão ({type(e).__name__})")
        time.sleep(3)

print("\nSem vaga nesta rodada. (A caça continua no próximo agendamento.)")
sys.exit(75)
