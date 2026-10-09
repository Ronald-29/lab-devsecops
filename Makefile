# Laboratorio DevSecOps: Terraform + Ansible + Greenbone
# Uso: make <objetivo>   (ejecuta "make help" para ver la lista)

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.RECIPEPREFIX = >

GB_COMPOSE ?= /home/ronal/greenbone-community-container/compose.yaml
GB_PROJECT ?= greenbone-community-edition
UMBRAL     ?= 7.0
ESCANER    := greenbone-community-edition-ospd-openvas-1 greenbone-community-edition-openvasd-1

.PHONY: help infra config conectar escanear lab desconectar destruir reconstruir

help:
> @echo "make infra        Terraform: crea la red y los servidores"
> echo "make config       Ansible: configura y endurece los servidores"
> echo "make conectar     Ansible: conecta Greenbone a la red del laboratorio"
> echo "make escanear     Greenbone: escanea y aplica el umbral (UMBRAL=$(UMBRAL))"
> echo "make lab          Todo lo anterior, en orden"
> echo "make destruir     Desconecta Greenbone y destruye la infraestructura"
> echo "make reconstruir  Destruye y vuelve a crear todo desde cero"

infra:
> terraform -chdir=terraform init -input=false
> terraform -chdir=terraform plan -input=false -out=plan.tfplan
> terraform -chdir=terraform apply -input=false plan.tfplan

config:
> cd ansible
> ansible objetivos -m ansible.builtin.wait_for_connection -a "timeout=60"
> ansible-playbook site.yml

conectar:
> cd ansible
> ansible-playbook greenbone.yml

escanear:
> test -n "$${GVM_PASSWORD:-}" || { echo "ERROR: define GVM_PASSWORD (read -rsp ... ; export GVM_PASSWORD)"; exit 1; }
> hosts=$$(terraform -chdir=terraform output -json servidores | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin).values()))')
> echo "Objetivos según Terraform: $$hosts"
> mkdir -p greenbone/reportes
> archivo=greenbone/reportes/escaneo-$$(date +%Y%m%d-%H%M).txt
> docker compose -f $(GB_COMPOSE) -p $(GB_PROJECT) run --rm -T \
>   -v "$(CURDIR)/greenbone:/scripts:ro" gvm-tools \
>   gvm-script --gmp-username admin --gmp-password "$$GVM_PASSWORD" \
>   socket /scripts/escanear.py $(UMBRAL) "$$hosts" | tee "$$archivo"
> echo "Reporte guardado en $$archivo"

lab: infra config conectar escanear

desconectar:
> for c in $(ESCANER); do
>   docker network disconnect lab-net "$$c" 2>/dev/null && echo "Desconectado: $$c" || true
> done

destruir: desconectar
> terraform -chdir=terraform destroy -auto-approve -input=false

reconstruir: destruir lab
