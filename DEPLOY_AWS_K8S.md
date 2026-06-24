# AutoVox AI AWS Kubernetes Deployment

This project is ready to deploy with Docker, AWS ECR, and AWS EKS.

## 1. Build locally

```bash
docker build -t autovox-ai .
docker run --rm -p 8000:8000 \
  -e DJANGO_DEBUG=False \
  -e DJANGO_SECRET_KEY=change-this \
  -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
  autovox-ai
```

Open `http://127.0.0.1:8000`.

## 2. Push image to AWS ECR

Create an ECR repository named `autovox-ai`, then run the push commands shown by AWS.

Example:

```bash
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com
docker tag autovox-ai:latest ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com/autovox-ai:latest
docker push ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com/autovox-ai:latest
```

## 3. Update Kubernetes image

Edit `k8s/deployment.yaml`:

```yaml
image: ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com/autovox-ai:latest
```

## 4. Create secret

Copy the example:

```bash
cp k8s/secret.example.yaml k8s/secret.yaml
```

Update `k8s/secret.yaml` with:

- `DJANGO_SECRET_KEY`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`

Do not commit `k8s/secret.yaml`.

## 5. Deploy to EKS

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

## 6. Later domain setup

After you buy a domain, point it to the AWS ALB created by the ingress.

For HTTPS, install AWS Load Balancer Controller and attach an ACM certificate.
