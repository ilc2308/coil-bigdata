# ==============================================================================
# Script de Despliegue y Ejecución en AWS Academy Learner Lab
# Sistema de Salud de Chernovia - Procesamiento Distribuido de Órdenes Médicas
# ==============================================================================

param (
    [Parameter(Mandatory=$true)]
    [string]$BucketName,
    
    [Parameter(Mandatory=$false)]
    [string]$AwsRegion = "us-east-1",
    
    [Parameter(Mandatory=$false)]
    [string]$LabRoleArn = ""
)

Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "DESPLIEGUE EN AWS ACADEMY LEARNER LAB - PROYECTO COIL BIG DATA" -ForegroundColor Cyan
Write-Host "Bucket S3: $BucketName | Región: $AwsRegion" -ForegroundColor Cyan
Write-Host "===================================================================" -ForegroundColor Cyan

# 1. Crear estructura de carpetas en S3
Write-Host "`n[1/5] Creando prefijos en S3..." -ForegroundColor Yellow
aws s3api put-object --bucket $BucketName --key bronze/solicitudes/ --region $AwsRegion
aws s3api put-object --bucket $BucketName --key catalogs/ --region $AwsRegion
aws s3api put-object --bucket $BucketName --key scripts/ --region $AwsRegion
aws s3api put-object --bucket $BucketName --key gold/curated_solicitudes/ --region $AwsRegion
aws s3api put-object --bucket $BucketName --key quarantine/solicitudes/ --region $AwsRegion
aws s3api put-object --bucket $BucketName --key athena-results/ --region $AwsRegion

# 2. Subir catálogos y script de Glue
Write-Host "`n[2/5] Subiendo catálogos y código Spark a S3..." -ForegroundColor Yellow
aws s3 cp dataset/COIL_catalogo_servicios_cubiertos.csv s3://$BucketName/catalogs/ --region $AwsRegion
aws s3 cp dataset/COIL_catalogo_perfiles_cobertura.csv s3://$BucketName/catalogs/ --region $AwsRegion
aws s3 cp src/aws_glue_job.py s3://$BucketName/scripts/aws_glue_job.py --region $AwsRegion

# 3. Subir archivo de órdenes (muestra o 1.2M)
Write-Host "`n[3/5] Subiendo dataset de órdenes a Capa Bronze (S3)..." -ForegroundColor Yellow
if (Test-Path "dataset/sample_1000.csv") {
    aws s3 cp dataset/sample_1000.csv s3://$BucketName/bronze/solicitudes/sample_1000.csv --region $AwsRegion
    Write-Host "  > Subido sample_1000.csv como prueba rápida." -ForegroundColor Green
}
if (Test-Path "dataset/COIL_dataset_glosas_salud_1_2M.csv") {
    Write-Host "  > Subiendo COIL_dataset_glosas_salud_1_2M.csv (puede tardar un momento)..." -ForegroundColor Yellow
    aws s3 cp dataset/COIL_dataset_glosas_salud_1_2M.csv s3://$BucketName/bronze/solicitudes/COIL_dataset_glosas_salud_1_2M.csv --region $AwsRegion
}

# 4. Desplegar CloudFormation Stack (o instrucciones manuales)
Write-Host "`n[4/5] Desplegando stack CloudFormation..." -ForegroundColor Yellow
if ($LabRoleArn -ne "") {
    aws cloudformation deploy `
        --template-file infrastructure/cloudformation_template.yaml `
        --stack-name coil-bigdata-salud-stack `
        --parameter-overrides LabRoleArn=$LabRoleArn `
        --capabilities CAPABILITY_IAM `
        --region $AwsRegion
} else {
    Write-Host "  > NOTA: Para desplegar por CloudFormation, pasa el parámetro -LabRoleArn." -ForegroundColor Yellow
    Write-Host "  > Alternativamente, en la consola de AWS Glue, crea el Job seleccionando 'LabRole' existente." -ForegroundColor Yellow
}

Write-Host "`n[5/5] Despliegue preparado exitosamente." -ForegroundColor Green
Write-Host "Para ejecutar el Job desde consola o CLI:" -ForegroundColor Cyan
Write-Host "aws glue start-job-run --job-name coil-bigdata-salud-spark-batch-processor --region $AwsRegion" -ForegroundColor White
