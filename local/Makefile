TF_DIR := terraform
ANSIBLE_DIR := ansible

.PHONY: bastion-tf-init bastion-tf-apply \
        ansible-deps bastion-bootstrap bastion-bootstrap-debug \
        all clean debug

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

bastion-bootstrap-debug: ansible-deps
	@if [ -z "$(GIT_BRANCH)" ]; then \
	  echo "Error: GIT_BRANCH is not set. Use: make debug GIT_BRANCH=<branch-name>"; \
	  exit 1; \
	fi
	cd $(ANSIBLE_DIR) && \
	  ansible-playbook -i localhost, site_local.yaml -e "git_branch=$(GIT_BRANCH)"

all: bastion-tf-init bastion-tf-apply bastion-bootstrap

debug: bastion-tf-init bastion-tf-apply bastion-bootstrap-debug

clean:
	@echo "==> Destroying bastion-01 from local..."
	cd $(TF_DIR) && terraform destroy -auto-approve || true
	rm -rf $(TF_DIR)/.terraform $(TF_DIR)/terraform.tfstate*

