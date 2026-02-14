CLUSTER_YAML := cluster.yaml

YQ := $(shell command -v yq 2>/dev/null)
CURL := $(shell command -v curl 2>/dev/null)

ifeq ($(strip $(YQ)),)
$(error yq is required but was not found in PATH. Install yq to use the root Makefile.)
endif

BASTION_USER       := $(shell $(YQ) -r '.login_user' $(CLUSTER_YAML))
BASTION_IP_PREFIX  := $(shell $(YQ) -r '.network.base_prefix' $(CLUSTER_YAML))
BASTION_VMID       := $(shell $(YQ) -r '.vms["bastion-01"].vmid' $(CLUSTER_YAML))
BASTION_HOST       := $(BASTION_IP_PREFIX).$(BASTION_VMID)
BASTION_HOMELAB_DIR ?= /home/$(BASTION_USER)/homelab

ALERTMANAGER_NTFY_BASE_URL := $(shell $(YQ) -r '.services[] | select(.name == "alertmanager") | .notifications.ntfy_base_url // empty' $(CLUSTER_YAML) | head -n1)
NTFY_PUB_HOST              := $(shell $(YQ) -r '.services[] | select(.name == "ntfy-pub") | .proxy.public_hostnames[0] // empty' $(CLUSTER_YAML) | head -n1)
NTFY_TOPIC_RAW             := $(shell $(YQ) -r '.services[] | select(.name == "alertmanager") | .notifications.ntfy_topic // empty' $(CLUSTER_YAML) | head -n1)

NTFY_NOTIFY_ENABLE ?= 1
NTFY_BASE_URL ?= $(if $(strip $(ALERTMANAGER_NTFY_BASE_URL)),$(strip $(ALERTMANAGER_NTFY_BASE_URL)),$(if $(strip $(NTFY_PUB_HOST)),https://$(strip $(NTFY_PUB_HOST)),))
NTFY_TOPIC ?= $(if $(strip $(NTFY_TOPIC_RAW)),$(strip $(NTFY_TOPIC_RAW)),alerts)
NTFY_NOTIFY_USER ?= $(shell $(YQ) -r '.secrets.alertmanager.ntfy_user // empty' $(CLUSTER_YAML))
NTFY_NOTIFY_PASS ?= $(shell $(YQ) -r '.secrets.alertmanager.ntfy_password // empty' $(CLUSTER_YAML))
NTFY_NOTIFY_TOKEN ?= $(shell $(YQ) -r '.secrets.alertmanager.ntfy_token // empty' $(CLUSTER_YAML))

.PHONY: local bastion all clean debug notify

local:
	@echo "==> Running local deployment..."
	cd local && $(MAKE) all

bastion:
	@echo "==> Executing 'make all' on bastion ($(BASTION_USER)@$(BASTION_HOST))..."
	@ssh $(BASTION_USER)@$(BASTION_HOST) \
	  'cd $(BASTION_HOMELAB_DIR)/bastion && make all'

all:
	@status=0; \
	$(MAKE) local || status=$$?; \
	if [ $$status -eq 0 ]; then $(MAKE) bastion || status=$$?; fi; \
	$(MAKE) notify TARGET=all STATUS=$$status; \
	exit $$status

debug:
	@if [ -z "$(GIT_BRANCH)" ]; then \
	  echo "Error: GIT_BRANCH is not set. Usage: make debug GIT_BRANCH=<branch-name>"; \
	  exit 1; \
	fi
	@status=0; \
	echo "==> Running local deployment with branch: $(GIT_BRANCH)..."; \
	$(MAKE) -C local debug GIT_BRANCH=$(GIT_BRANCH) || status=$$?; \
	if [ $$status -eq 0 ]; then \
	  echo "==> Executing 'make all' on bastion ($(BASTION_USER)@$(BASTION_HOST))..."; \
	  ssh $(BASTION_USER)@$(BASTION_HOST) 'cd $(BASTION_HOMELAB_DIR)/bastion && make all' || status=$$?; \
	fi; \
	$(MAKE) notify TARGET=debug STATUS=$$status; \
	exit $$status

notify:
	@if [ "$(NTFY_NOTIFY_ENABLE)" != "1" ]; then \
	  exit 0; \
	fi
	@if [ -z "$(CURL)" ]; then \
	  echo "==> WARN: curl not found; skipping notification."; \
	  exit 0; \
	fi
	@if [ -z "$(strip $(NTFY_BASE_URL))" ]; then \
	  echo "==> WARN: NTFY_BASE_URL is empty; skipping notification."; \
	  exit 0; \
	fi
	@status="$(STATUS)"; \
	target="$(TARGET)"; \
	if [ "$$status" -eq 0 ]; then \
	  title="homelab $$target SUCCESS"; \
	  priority="3"; \
	  tags="white_check_mark,hammer_and_wrench"; \
	  body="make $$target succeeded on $$(hostname)"; \
	else \
	  title="homelab $$target FAILED"; \
	  priority="5"; \
	  tags="x,hammer_and_wrench"; \
	  body="make $$target failed on $$(hostname) (exit=$$status)"; \
	fi; \
	if [ -n "$(strip $(NTFY_NOTIFY_TOKEN))" ]; then \
	  $(CURL) -fsS -X POST "$(NTFY_BASE_URL)/$(NTFY_TOPIC)" \
	    -H "Authorization: Bearer $(NTFY_NOTIFY_TOKEN)" \
	    -H "Title: $$title" \
	    -H "Priority: $$priority" \
	    -H "Tags: $$tags" \
	    --data "$$body" >/dev/null || echo "==> WARN: notification failed."; \
	elif [ -n "$(strip $(NTFY_NOTIFY_USER))" ] && [ -n "$(strip $(NTFY_NOTIFY_PASS))" ]; then \
	  $(CURL) -fsS -X POST "$(NTFY_BASE_URL)/$(NTFY_TOPIC)" \
	    -u "$(NTFY_NOTIFY_USER):$(NTFY_NOTIFY_PASS)" \
	    -H "Title: $$title" \
	    -H "Priority: $$priority" \
	    -H "Tags: $$tags" \
	    --data "$$body" >/dev/null || echo "==> WARN: notification failed."; \
	else \
	  $(CURL) -fsS -X POST "$(NTFY_BASE_URL)/$(NTFY_TOPIC)" \
	    -H "Title: $$title" \
	    -H "Priority: $$priority" \
	    -H "Tags: $$tags" \
	    --data "$$body" >/dev/null || echo "==> WARN: notification failed."; \
	fi

clean:
	@echo "==> Cleaning bastion..."
	@ssh $(BASTION_USER)@$(BASTION_HOST) 'cd $(BASTION_HOMELAB_DIR)/bastion && make clean' || \
		echo "==> WARN: Could not execute clean on bastion (it may already be broken/unreachable). Continuing..."
	@echo "==> Cleaning local..."
	cd local && $(MAKE) clean
