#!/bin/bash
# Persist umask 0002 so all ARM child processes create group-writable files.
grep -q 'umask 0002' /etc/bash.bashrc 2>/dev/null || echo 'umask 0002' >> /etc/bash.bashrc
grep -q 'umask 0002' /home/arm/.profile 2>/dev/null || echo 'umask 0002' >> /home/arm/.profile
umask 0002
