CLUSTER_YAML := cluster.yaml

BASTION_USER       := $(shell yq -r '.login_user' $(CLUSTER_YAML))
BASTION_IP_PREFIX  := $(shell yq -r '.network.base_prefix' $(CLUSTER_YAML))
BASTION_VMID       := $(shell yq -r '.vms["bastion-01"].vmid' $(CLUSTER_YAML))
BASTION_HOST       := $(BASTION_IP_PREFIX).$(BASTION_VMID)
BASTION_HOMELAB_DIR ?= /home/$(BASTION_USER)/homelab

.PHONY: local bastion all clean debug

local:
	@echo "==> Running local deployment..."
	cd local && $(MAKE) all

bastion:
	@echo "==> Executing 'make all' on bastion ($(BASTION_USER)@$(BASTION_HOST))..."
	@ssh $(BASTION_USER)@$(BASTION_HOST) \
	  'cd $(BASTION_HOMELAB_DIR)/bastion && make all'

all: local bastion

debug:
	@if [ -z "$(GIT_BRANCH)" ]; then \
	  echo "Error: GIT_BRANCH is not set. Usage: make debug GIT_BRANCH=<branch-name>"; \
	  exit 1; \
	fi
	@echo "==> Running local deployment with branch: $(GIT_BRANCH)..."
	cd local && $(MAKE) debug GIT_BRANCH=$(GIT_BRANCH)
	@echo "==> Executing 'make all' on bastion ($(BASTION_USER)@$(BASTION_HOST))..."
	@ssh $(BASTION_USER)@$(BASTION_HOST) \
	  'cd $(BASTION_HOMELAB_DIR)/bastion && make all'

clean:
	@echo "==> Cleaning bastion..."
	@ssh $(BASTION_USER)@$(BASTION_HOST) 'cd $(BASTION_HOMELAB_DIR)/bastion && make clean' || \
		echo "==> WARN: Could not execute clean on bastion (it may already be broken/unreachable). Continuing..."
	@echo "==> Cleaning local..."
	cd local && $(MAKE) clean
