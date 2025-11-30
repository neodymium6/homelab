TF_DIR := terraform
ANSIBLE_DIR := ansible

CLUSTER_YAML := ../cluster.yaml

BASTION_USER       := $(shell yq -r '.login_user' $(CLUSTER_YAML))
BASTION_IP_PREFIX  := $(shell yq -r '.network.base_prefix' $(CLUSTER_YAML))
BASTION_VMID       := $(shell yq -r '.vms["bastion-01"].vmid' $(CLUSTER_YAML))
BASTION_HOST       := $(BASTION_IP_PREFIX).$(BASTION_VMID)
BASTION_HOMELAB_DIR ?= /home/$(BASTION_USER)/homelab

.PHONY: bastion-tf-init bastion-tf-apply \
        ansible-deps bastion-bootstrap bastion-all-remote \
        all clean bastion-clean-remote

bastion-tf-init:
	cd $(TF_DIR) && terraform init

bastion-tf-apply:
	cd $(TF_DIR) && terraform apply -auto-approve

ansible-deps:
	cd $(ANSIBLE_DIR) && \
	  ansible-galaxy collection install community.general community.crypto

bastion-bootstrap: ansible-deps
	cd $(ANSIBLE_DIR) && \
	  ansible-playbook -i localhost, site_local.yaml

bastion-all-remote:
	@echo "==> Executing 'make all' on bastion ($(BASTION_USER)@$(BASTION_HOST))..."
	@ssh $(BASTION_USER)@$(BASTION_HOST) \
	  'cd $(BASTION_HOMELAB_DIR)/bastion && make all'

all: bastion-tf-init bastion-tf-apply bastion-bootstrap bastion-all-remote

bastion-clean-remote:
	@echo "==> Executing 'make clean' on bastion ($(BASTION_USER)@$(BASTION_HOST))..."
	@ssh $(BASTION_USER)@$(BASTION_HOST) 'cd $(BASTION_HOMELAB_DIR)/bastion && make clean' || \
		echo "==> WARN: Could not execute clean on bastion (it may already be broken/unreachable). Continuing..."

clean: bastion-clean-remote
	@echo "==> Destroying bastion-01 from local..."
	cd $(TF_DIR) && terraform destroy -auto-approve || true
	rm -rf $(TF_DIR)/.terraform $(TF_DIR)/terraform.tfstate*

