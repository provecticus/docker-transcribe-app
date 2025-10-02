# Deployment Guide: Quick Transcription Web App

This guide covers deploying the app to a live server for team access. All options use Docker for consistency. Costs are ~$3-5/mo for basics. Share the URL (e.g., `http://YOUR_IP`) via email/Slack.

## Prerequisites (All Options)
- Docker installed on target machine.
- Git repo cloned: `git clone <your-repo> && cd transcribe-app`.
- Firewall: Open port 80/5000 (TCP inbound).
- Domain (optional): Use free dynamic DNS (e.g., No-IP) for static URL.

## Option 1: Local Windows Machine (Dev/Testing—Free, 5 Min)
For quick team shares on your network.
1. **Install Docker Desktop**: [Download](https://www.docker.com/products/docker-desktop/). Restart.
2. **Build & Run**:

docker build -t transcribe-app .
docker run -d -p 80:5000 --restart=always --name transcribe-1 -v $(pwd)/uploads:/app/uploads transcribe-app

3. **Access**: `http://YOUR_LOCAL_IP` (find IP: `ipconfig` > IPv4).
4. **Pros/Cons**: Free, but machine must stay on. Pros: No cloud setup.
5. **Firewall**: Windows Defender > Inbound Rules > New > Port 80 TCP > Allow.
6. **Backup**: `docker commit transcribe-1 transcribe-backup:v1` (saves image).

## Option 2: AWS Lightsail (Recommended—$3.50/mo, 10 Min)
Scalable VPS; free tier for first month.
1. **Create Instance**:
- [lightsail.aws.amazon.com](https://lightsail.aws.amazon.com/) > Sign in (free account).
- "Create instance" > Platform: Linux/Unix > Blueprint: Amazon Linux 2023 > Instance size: Nano (0.5GB RAM, $3.50/mo) > Create.
- Download SSH key (.pem) from dashboard.
2. **SSH & Setup Docker** (3 min):

ssh -i your-key.pem ec2-user@YOUR_INSTANCE_IP
sudo yum update -y && sudo yum install docker -y
sudo systemctl start docker && sudo systemctl enable docker
sudo usermod -aG docker ec2-user  # Relogin: exit + ssh again

**Deploy**:
git clone <your-repo> && cd transcribe-app
docker build -t transcribe-app .
docker run -d -p 80:5000 --restart=always --name transcribe-1 -v $(pwd)/uploads:/app/uploads transcribe-app

4. **Networking**: Lightsail Dashboard > Instance > Networking tab > Add rule: HTTP (80) > Save.
5. **Access**: `http://YOUR_INSTANCE_IP` (public IP from dashboard).
6. **Pros/Cons**: Auto-backups, scalable (upgrade RAM). Cons: AWS account needed.
7. **Costs**: $3.50/mo + data out (~$0.09/GB). Stop instance to pause billing.
8. **Backup**: Lightsail snapshot (dashboard > Snapshots > Create).

## Option 3: DigitalOcean Droplet ($4/mo, 10 Min)
Similar to AWS; simpler UI.
1. **Create Droplet**:
- [cloud.digitalocean.com](https://cloud.digitalocean.com/registrations/new) > Sign up (free $200 credit).
- "Create Droplet" > Image: Ubuntu 24.04 > Plan: Basic $4/mo (1GB RAM) > VPC: Default > Create.
- Note root password/email from dashboard.
2. **SSH & Setup Docker**:
ssh root@YOUR_DROPLET_IP
apt update && apt install docker.io -y
systemctl start docker && systemctl enable docker
usermod -aG docker root  # Relogin
3. **Deploy**: Same as AWS Step 3.
4. **Firewall**: Dashboard > Droplet > Networking > Firewalls > Add: Inbound TCP 80 > Apply.
5. **Access**: `http://YOUR_DROPLET_IP`.
6. **Pros/Cons**: $200 credit (free 2+ mo), easy snapshots. Cons: Slightly pricier base.
7. **Costs**: $4/mo + $0.01/GB out. Destroy to stop.
8. **Backup**: Dashboard > Backups > Enable weekly ($0.60/mo).

## Option 4: Existing Windows Server (Internal—Free, 10 Min)
If you have a dedicated server.
1. **Install Docker Desktop**: Same as Local (admin rights).
2. **Deploy**: Same as Local, but `-p 80:5000` (run as admin for low port).
3. **Static IP**: Server settings > Network > Set static IPv4.
4. **Access**: `http://SERVER_STATIC_IP`.
5. **Pros/Cons**: No cloud costs; internal network only (use VPN for remote). Pros: Full control.
6. **Firewall**: Inbound Rule for port 80.
7. **Backup**: Use Windows Backup + `docker save transcribe-app > app.tar`.

## Production Tips (All Options)
- **HTTPS**: Add Nginx container: `docker run -d -p 443:443 --link transcribe-1 nginx` (config for proxy + certbot).
- **Auth**: Edit app.py: `pip install flask-httpauth` in Dockerfile; add login route.
- **Monitoring**: Portainer: `docker run -d -p 9000:9000 --restart=always -v /var/run/docker.sock:/var/run/docker.sock portainer/portainer-ce` > `http://IP:9000`.
- **Updates**: Pull repo, rebuild, restart container.
- **Costs Summary**:
| Option | Monthly Cost | Setup Time | Scalability |
|--------|--------------|------------|-------------|
| Local Windows | $0 | 5 min | Low |
| AWS Lightsail | $3.50 | 10 min | High |
| DigitalOcean | $4 | 10 min | High |
| Windows Server | $0 (if owned) | 10 min | Medium |

For help: Check logs (`docker logs -f transcribe-1`) or ping the team.