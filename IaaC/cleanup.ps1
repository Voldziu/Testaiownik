#!/usr/bin/env pwsh
# Script for cleaning up TESTAIOWNIK infrastructure

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "prod")]
    [string]$Environment,
    
    [Parameter(Mandatory = $false)]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory = $false)]
    [string]$ProjectName = "testaiownik",
    
    [Parameter(Mandatory = $false)]
    [switch]$WhatIf,
    
    [Parameter(Mandatory = $false)]
    [switch]$Force
)

# Colors for output
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"

function Write-ColorOutput($Color, $Message) {
    Write-Host $Message -ForegroundColor $Color
}

Write-ColorOutput $Red "🧹 Starting cleanup for TESTAIOWNIK"
Write-ColorOutput $Yellow "Environment: $Environment"
Write-ColorOutput $Yellow "Project: $ProjectName"

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

# Resource group name
$resourceGroupName = "$ProjectName-$Environment"

# Check if resource group exists
try {
    $rg = Get-AzResourceGroup -Name $resourceGroupName -ErrorAction Stop
    Write-ColorOutput $Yellow "📋 Found resource group: $resourceGroupName"
    Write-ColorOutput $Yellow "   Location: $($rg.Location)"
    Write-ColorOutput $Yellow "   Resources: $($rg.Tags.Count) tags"
    
    # List resources in the group
    $resources = Get-AzResource -ResourceGroupName $resourceGroupName
    Write-ColorOutput $Yellow "`n📦 Resources to be deleted:"
    foreach ($resource in $resources) {
        Write-Host "   - $($resource.Name) ($($resource.ResourceType))"
    }
    Write-Host ""
    
} catch {
    Write-ColorOutput $Yellow "⚠️  Resource group '$resourceGroupName' not found or already deleted"
    exit 0
}
# Confirmation prompt
if (-not $Force -and -not $WhatIf) {
    Write-ColorOutput $Red "⚠️  WARNING: This will permanently delete ALL resources in '$resourceGroupName'"
    Write-ColorOutput $Red "   This action CANNOT be undone!"
    $confirmation = Read-Host "`nType 'DELETE' to confirm deletion"
    
    if ($confirmation -ne "DELETE") {
        Write-ColorOutput $Yellow "❌ Deletion cancelled"
        exit 0
    }
}

# Execute cleanup
try {
    if ($WhatIf) {
        Write-ColorOutput $Yellow "🔍 What-If: Would delete resource group '$resourceGroupName' and all its resources"
        Write-ColorOutput $Yellow "   This includes:"
        foreach ($resource in $resources) {
            Write-Host "   - $($resource.Name) ($($resource.ResourceType))"
        }
    } else {
        Write-ColorOutput $Red "🗑️  Deleting resource group '$resourceGroupName'..."
        
        Remove-AzResourceGroup -Name $resourceGroupName -Force -Verbose
        
        Write-ColorOutput $Green "✅ Resource group '$resourceGroupName' deleted successfully!"
        Write-ColorOutput $Green "🎉 Cleanup completed!"
        
        Write-ColorOutput $Yellow "`n📝 Don't forget to:"
        Write-Host "   - Remove any local .env files"
        Write-Host "   - Clear any cached credentials"
        Write-Host "   - Update your documentation"
    }
} catch {
    Write-ColorOutput $Red "❌ Error during cleanup: $($_.Exception.Message)"
    exit 1
}

Write-ColorOutput $Green "🏁 Cleanup script finished!"