# 0002 Build environment
Problem: Windows host has no Linux builder. Chosen: build in an Arch VM (VMware Workstation, already installed; VirtualBox service is disabled) and in GitHub Actions with an Arch container. WSL/docker not installed, so not used. Revisit if CI proves unreliable for privileged mkarchiso.
