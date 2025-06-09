#!/usr/bin/env pwsh
# Script for deploying infrastructure for TESTAIOWNIK

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "prod")]
    [string]$Environment,
    
    [Parameter(Mandatory = $false)]
    [string]$SubscriptionId, 
    
    [Parameter(Mandatory = $false)]
    [string]$Location = "swedencentral",
    
    [Parameter(Mandatory = $false)]
    [switch]$WhatIf
)

# Colors for output
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"

function Write-ColorOutput($Color, $Message) {
    Write-Host $Message -ForegroundColor $Color
}


Write-ColorOutput $Green "🚀 Starting the development for TESTAIOWNIK"
Write-ColorOutput $Yellow "Environment: $Environment"
Write-ColorOutput $Yellow "Location: $Location"

# Check if the user is logged in to Azure
try {
    $context = Get-AzContext
    if (-not $context) {
        throw "You are not logged in to Azure"
    }
    Write-ColorOutput $Green "✅ Logged in as: $($context.Account.Id)"
} catch {
    Write-ColorOutput $Red "❌ Error: $($_.Exception.Message)"
    Write-Host "Run: Connect-AzAccount"
    exit 1
}

# Set subscription if provided
if ($SubscriptionId) {
    try {
        Set-AzContext -SubscriptionId $SubscriptionId
        Write-ColorOutput $Green "✅ Set subscription: $SubscriptionId"
    } catch {
        Write-ColorOutput $Red "❌ Cannot set subscription: $SubscriptionId"
        exit 1
    }
}

# Check if the environment variable for DB password exists
if (-not $env:DB_ADMIN_PASSWORD) {
    Write-ColorOutput $Yellow "⚠️  DB_ADMIN_PASSWORD variable not found"
    $securePassword = Read-Host "Enter database admin password" -AsSecureString
    $env:DB_ADMIN_PASSWORD = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword))
}

# Deployment parameters
$deploymentName = "testaiownik-deployment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$parametersFile = "parameters/$Environment.bicepparam"

# Check if the parameters file exists
if (-not (Test-Path $parametersFile)) {
    Write-ColorOutput $Red "❌ Parameters file not found: $parametersFile"
    exit 1
}

Write-ColorOutput $Yellow "📁 Using parameters file: $parametersFile"

# Execute deployment
try {
    if ($WhatIf) {
        Write-ColorOutput $Yellow "🔍 Executing What-If deployment..."
        $result = New-AzSubscriptionDeployment `
            -Name $deploymentName `
            -Location $Location `
            -TemplateFile "main.bicep" `
            -TemplateParameterFile $parametersFile `
            -WhatIf
    }
     else {
        Write-ColorOutput $Yellow "🔄 Executing deployment..."
        $result = New-AzSubscriptionDeployment `
            -Name $deploymentName `
            -Location $Location `
            -TemplateFile "main.bicep" `
            -TemplateParameterFile $parametersFile `
            -Verbose
        
        if ($result.ProvisioningState -eq "Succeeded") {
            Write-ColorOutput $Green "✅ Deployment completed successfully!"
        } else {
            Write-ColorOutput $Red "❌ Deployment failed!"
            exit 1
        }
    }
} catch {
    Write-ColorOutput $Red "❌ Error during deployment: $($_.Exception.Message)"
    exit 1
}

Write-ColorOutput $Green "🎉 Done!"