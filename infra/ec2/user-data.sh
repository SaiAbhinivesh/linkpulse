#!/bin/bash
# Runs once, at first boot. Installs k3s (lightweight Kubernetes).
# --tls-san adds the public IP to the API certificate, so kubectl on a laptop can connect.
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --tls-san YOUR_EC2_IP --write-kubeconfig-mode 644" sh -