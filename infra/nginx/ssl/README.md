# Certificados SSL do nginx (produção)

Este diretório é montado no container nginx em `/etc/nginx/ssl` (veja
`docker-compose.prod.yml`, serviço `nginx`) e **não deve conter segredos no
repositório** — os certificados reais ficam fora do controle de versão.

## Nomes de arquivo esperados

O `infra/nginx/nginx.conf` referencia exatamente estes dois arquivos:

- `cert.pem` — certificado (fullchain) → `ssl_certificate /etc/nginx/ssl/cert.pem;`
- `key.pem` — chave privada → `ssl_certificate_key /etc/nginx/ssl/key.pem;`

Ou seja, os arquivos devem existir neste diretório como:

```
infra/nginx/ssl/cert.pem
infra/nginx/ssl/key.pem
```

## Opção 1 — Let's Encrypt / certbot

Gerar o certificado com certbot (modo standalone, com o nginx parado ou
usando o plugin webroot) e copiar os arquivos gerados para cá:

```bash
sudo certbot certonly --standalone -d medsafe.app -d www.medsafe.app

# Copiar/renomear para os nomes esperados pelo nginx.conf
sudo cp /etc/letsencrypt/live/medsafe.app/fullchain.pem infra/nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/medsafe.app/privkey.pem   infra/nginx/ssl/key.pem
```

Configure a renovação automática (cron/systemd timer) do certbot e repita a
cópia acima (ou crie symlinks) após cada renovação, seguida de
`docker compose -f docker-compose.prod.yml restart nginx`.

## Opção 2 — Certificado fornecido pela clínica/CA própria

Caso a clínica forneça um certificado (ex.: emitido por uma CA interna ou
contratada), basta colocar os arquivos com os mesmos nomes:

```bash
cp /caminho/para/certificado-fornecido.pem infra/nginx/ssl/cert.pem
cp /caminho/para/chave-privada.pem         infra/nginx/ssl/key.pem
```

Se o certificado vier separado da cadeia intermediária, concatene-os em
`cert.pem` na ordem: certificado da aplicação seguido da cadeia
intermediária (fullchain).

## Permissões

Restrinja a leitura da chave privada:

```bash
chmod 600 infra/nginx/ssl/key.pem
```

## Observação

Este diretório contém apenas um `.gitkeep` para existir no repositório. Nunca
commite `cert.pem` ou `key.pem` reais.
