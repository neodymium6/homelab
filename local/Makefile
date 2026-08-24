TF_DIR := terraform
ANSIBLE_DIR := ansible

.PHONY: bastion-tf-init bastion-tf-apply \
        ansible-deps bastion-bootstrap bastion-bootstrap-debug \
        audiomuse-worker-configure \
        audiomuse-worker-up audiomuse-worker-down audiomuse-worker-logs audiomuse-worker-status \
        audiomuse-refresh \
        all clean debug

AUDIOMUSE_WORKER_DIR := /opt/stacks/audiomuse-worker
AUDIOMUSE_WORKER_COMPOSE := $(AUDIOMUSE_WORKER_DIR)/docker-compose.yaml
AUDIOMUSE_WORKER_ENV := $(AUDIOMUSE_WORKER_DIR)/.env

bastion-tf-init:
	cd $(TF_DIR) && terraform init

bastion-tf-apply:
	cd $(TF_DIR) && terraform apply -auto-approve

ansible-deps:
	cd $(ANSIBLE_DIR) && \
	  ansible-galaxy collection install ansible.posix community.general community.crypto community.docker

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

audiomuse-worker-configure: ansible-deps
	cd $(ANSIBLE_DIR) && \
	  ansible-playbook -i localhost, site_local.yaml --tags audiomuse_worker --ask-become-pass

audiomuse-worker-up:
	sudo docker compose --env-file $(AUDIOMUSE_WORKER_ENV) -f $(AUDIOMUSE_WORKER_COMPOSE) up -d --remove-orphans

audiomuse-worker-down:
	sudo docker compose --env-file $(AUDIOMUSE_WORKER_ENV) -f $(AUDIOMUSE_WORKER_COMPOSE) down

audiomuse-worker-logs:
	sudo docker compose --env-file $(AUDIOMUSE_WORKER_ENV) -f $(AUDIOMUSE_WORKER_COMPOSE) logs -f worker

audiomuse-worker-status:
	sudo docker compose --env-file $(AUDIOMUSE_WORKER_ENV) -f $(AUDIOMUSE_WORKER_COMPOSE) ps

audiomuse-refresh:
	./scripts/audiomuse-refresh.sh

clean:
	@echo "==> Destroying bastion-01 from local..."
	cd $(TF_DIR) && terraform destroy -auto-approve || true
	rm -rf $(TF_DIR)/.terraform $(TF_DIR)/terraform.tfstate*
