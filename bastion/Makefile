TF_DIR := terraform
ANSIBLE_DIR := ansible

ANSIBLE_VENV_BIN ?= $(HOME)/.venv/ansible/bin
ANSIBLE_PLAYBOOK ?= $(ANSIBLE_VENV_BIN)/ansible-playbook
ANSIBLE_GALAXY   ?= $(ANSIBLE_VENV_BIN)/ansible-galaxy
TERRAFORM        ?= /usr/local/bin/terraform

.PHONY: dns-check dns-apply tf-init tf-apply \
        ansible-deps bastion-setup internal-setup \
				homemanager \
        all clean

tf-init:
	cd $(TF_DIR) && $(TERRAFORM) init

# Existing DNS hosts only; does not provision VMs, install packages, or alter AGH.
dns-check:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) -i localhost, site_internal.yaml \
	  --limit 'localhost,dns' --tags service-dns --check --diff

dns-apply:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) -i localhost, site_internal.yaml \
	  --limit 'localhost,dns' --tags service-dns

tf-apply:
	cd $(TF_DIR) && $(TERRAFORM) apply -auto-approve

ansible-deps:
	cd $(ANSIBLE_DIR) && \
	  $(ANSIBLE_GALAXY) collection install ansible.posix community.general community.crypto community.docker

bastion-setup: ansible-deps
	cd $(ANSIBLE_DIR) && \
	  $(ANSIBLE_PLAYBOOK) -i localhost, site_bastion.yaml

internal-setup: ansible-deps
	cd $(ANSIBLE_DIR) && \
	  $(ANSIBLE_PLAYBOOK) -i localhost, site_internal.yaml

homemanager: ansible-deps
	cd $(ANSIBLE_DIR) && \
	  $(ANSIBLE_PLAYBOOK) -i localhost, site_homemanager.yaml

all: tf-init bastion-setup tf-apply internal-setup homemanager

clean:
	cd $(TF_DIR) && $(TERRAFORM) destroy -auto-approve || true
	rm -rf $(TF_DIR)/.terraform $(TF_DIR)/terraform.tfstate*
	rm -f $(HOME)/.ssh/id_ed25519_internal $(HOME)/.ssh/id_ed25519_internal.pub
