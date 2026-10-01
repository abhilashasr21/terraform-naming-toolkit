#!/usr/bin/env python3
"""Build catalogs/azure-caf.json from Microsoft's CAF abbreviation guidance.

This script embeds Microsoft's *public* Cloud Adoption Framework (CAF)
recommendations and emits a machine-readable catalog the converter can use as a
fallback source of abbreviations and Terraform mappings when a customer's
workbook does not define its own.

Sources (Microsoft Learn, public):
  * Abbreviation recommendations for Azure resources
    https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations
  * Define your naming convention
    https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming

Offline, standard-library only. Re-run after updating the tables below:

    python catalogs/build_caf_catalog.py

Each resource row is (label, arm_namespace, abbreviation, terraform_types, scope).
`terraform_types` is populated for the common core; where a mapping is ambiguous
or provider-version dependent it is left empty but the abbreviation is still
available by label. `scope` is set only where CAF explicitly documents a Global
uniqueness scope; otherwise it is null and the customer's constraint sheet wins.
"""

from __future__ import annotations

import json
from pathlib import Path

# Source metadata (update ms_page_date when refreshing from Microsoft Learn).
SOURCE = {
    "name": "Azure Cloud Adoption Framework (CAF) resource abbreviations",
    "abbreviations_url": "https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations",
    "naming_url": "https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming",
    "ms_page_date": "2025-05-23",
    "captured": "2026-10-01",
}

# CAF recommended component order and delimiter (from the naming-convention page).
COMPONENT_ORDER = ["resource", "workload", "environment", "region", "instance"]
DELIMITER = "-"

# CAF environment examples: prod, dev, qa, stage, test.
DEFAULT_CODE_SETS = {
    "environment": {
        "prod": "prod",
        "dev": "dev",
        "qa": "qa",
        "stage": "stage",
        "test": "test",
    }
}

G = "global"            # unique across all Azure (public DNS endpoint)
RG = "resource_group"   # unique within the resource group
R = "resource"          # unique within the parent resource

# (label, arm_namespace, abbreviation, terraform_types, scope)
RESOURCES: list[tuple[str, str, str, list[str], str | None]] = [
    # --- AI + machine learning ---
    ("AI Search", "Microsoft.Search/searchServices", "srch", ["azurerm_search_service"], G),
    ("Foundry Tools (multi-service account)", "Microsoft.CognitiveServices/accounts", "ais", ["azurerm_cognitive_account"], None),
    ("Foundry account", "Microsoft.CognitiveServices/accounts", "aif", [], None),
    ("Foundry hub", "Microsoft.MachineLearningServices/workspaces", "hub", [], None),
    ("Azure AI Video Indexer", "Microsoft.VideoIndexer/accounts", "avi", [], None),
    ("Azure Machine Learning workspace", "Microsoft.MachineLearningServices/workspaces", "mlw", ["azurerm_machine_learning_workspace"], None),
    ("Azure OpenAI Service", "Microsoft.CognitiveServices/accounts", "oai", [], None),
    ("Bot service", "Microsoft.BotService/botServices", "bot", ["azurerm_bot_service_azure_bot"], None),
    ("Computer vision", "Microsoft.CognitiveServices/accounts", "cv", [], None),
    ("Content moderator", "Microsoft.CognitiveServices/accounts", "cm", [], None),
    ("Content safety", "Microsoft.CognitiveServices/accounts", "cs", [], None),
    ("Document intelligence", "Microsoft.CognitiveServices/accounts", "di", [], None),
    ("Face API", "Microsoft.CognitiveServices/accounts", "face", [], None),
    ("Health Insights", "Microsoft.CognitiveServices/accounts", "hi", [], None),
    ("Immersive reader", "Microsoft.CognitiveServices/accounts", "ir", [], None),
    ("Language service", "Microsoft.CognitiveServices/accounts", "lang", [], None),
    ("Speech service", "Microsoft.CognitiveServices/accounts", "spch", [], None),
    ("Translator", "Microsoft.CognitiveServices/accounts", "trsl", [], None),

    # --- Analytics and IoT ---
    ("Azure Analysis Services server", "Microsoft.AnalysisServices/servers", "as", ["azurerm_analysis_services_server"], None),
    ("Azure Databricks workspace", "Microsoft.Databricks/workspaces", "dbw", ["azurerm_databricks_workspace"], None),
    ("Azure Data Explorer cluster", "Microsoft.Kusto/clusters", "dec", ["azurerm_kusto_cluster"], None),
    ("Azure Data Explorer cluster database", "Microsoft.Kusto/clusters/databases", "dedb", ["azurerm_kusto_database"], None),
    ("Azure Data Factory", "Microsoft.DataFactory/factories", "adf", ["azurerm_data_factory"], G),
    ("Azure Digital Twin instance", "Microsoft.DigitalTwins/digitalTwinsInstances", "dt", ["azurerm_digital_twins_instance"], None),
    ("Azure Stream Analytics", "Microsoft.StreamAnalytics/cluster", "asa", ["azurerm_stream_analytics_cluster"], None),
    ("Azure Synapse Analytics SQL Dedicated Pool", "Microsoft.Synapse/workspaces/sqlPools", "syndp", ["azurerm_synapse_sql_pool"], None),
    ("Azure Synapse Analytics Spark Pool", "Microsoft.Synapse/workspaces/bigDataPools", "synsp", ["azurerm_synapse_spark_pool"], None),
    ("Azure Synapse Analytics workspaces", "Microsoft.Synapse/workspaces", "synw", ["azurerm_synapse_workspace"], None),
    ("Data Lake Store account", "Microsoft.DataLakeStore/accounts", "dls", ["azurerm_data_lake_store"], G),
    ("Event Hubs namespace", "Microsoft.EventHub/namespaces", "evhns", ["azurerm_eventhub_namespace"], G),
    ("Event hub", "Microsoft.EventHub/namespaces/eventHubs", "evh", ["azurerm_eventhub"], None),
    ("Event hub consumer group", "Microsoft.EventHub/namespaces/eventhubs/consumerGroups", "evhcg", ["azurerm_eventhub_consumer_group"], None),
    ("Event Grid domain", "Microsoft.EventGrid/domains", "evgd", ["azurerm_eventgrid_domain"], None),
    ("Event Grid subscriptions", "Microsoft.EventGrid/eventSubscriptions", "evgs", ["azurerm_eventgrid_event_subscription"], None),
    ("Event Grid topic", "Microsoft.EventGrid/domains/topics", "evgt", ["azurerm_eventgrid_domain_topic"], None),
    ("Event Grid system topic", "Microsoft.EventGrid/systemTopics", "egst", ["azurerm_eventgrid_system_topic"], None),
    ("HDInsight - Hadoop cluster", "Microsoft.HDInsight/clusters", "hadoop", ["azurerm_hdinsight_hadoop_cluster"], None),
    ("HDInsight - HBase cluster", "Microsoft.HDInsight/clusters", "hbase", ["azurerm_hdinsight_hbase_cluster"], None),
    ("HDInsight - Kafka cluster", "Microsoft.HDInsight/clusters", "kafka", ["azurerm_hdinsight_kafka_cluster"], None),
    ("HDInsight - Spark cluster", "Microsoft.HDInsight/clusters", "spark", ["azurerm_hdinsight_spark_cluster"], None),
    ("IoT hub", "Microsoft.Devices/IotHubs", "iot", ["azurerm_iothub"], G),
    ("Provisioning services", "Microsoft.Devices/provisioningServices", "provs", ["azurerm_iothub_dps"], None),
    ("Power BI Embedded", "Microsoft.PowerBIDedicated/capacities", "pbi", ["azurerm_powerbi_embedded"], None),
    ("Time Series Insights environment", "Microsoft.TimeSeriesInsights/environments", "tsi", ["azurerm_iot_time_series_insights_gen2_environment"], None),

    # --- Compute and web ---
    ("App Service environment", "Microsoft.Web/hostingEnvironments", "ase", ["azurerm_app_service_environment_v3"], None),
    ("App Service plan", "Microsoft.Web/serverFarms", "asp", ["azurerm_service_plan"], None),
    ("Azure Load Testing instance", "Microsoft.LoadTestService/loadTests", "lt", ["azurerm_load_test"], None),
    ("Availability set", "Microsoft.Compute/availabilitySets", "avail", ["azurerm_availability_set"], None),
    ("Azure Arc enabled server", "Microsoft.HybridCompute/machines", "arcs", [], None),
    ("Azure Arc enabled Kubernetes cluster", "Microsoft.Kubernetes/connectedClusters", "arck", [], None),
    ("Batch accounts", "Microsoft.Batch/batchAccounts", "ba", ["azurerm_batch_account"], None),
    ("Communication Services", "Microsoft.Communication/communicationServices", "acs", ["azurerm_communication_service"], G),
    ("Disk encryption set", "Microsoft.Compute/diskEncryptionSets", "des", ["azurerm_disk_encryption_set"], None),
    ("Function app", "Microsoft.Web/sites", "func", ["azurerm_linux_function_app", "azurerm_windows_function_app"], G),
    ("Gallery", "Microsoft.Compute/galleries", "gal", ["azurerm_shared_image_gallery"], None),
    ("Managed disk (data)", "Microsoft.Compute/disks", "disk", ["azurerm_managed_disk"], None),
    ("Notification Hubs", "Microsoft.NotificationHubs/namespaces/notificationHubs", "ntf", ["azurerm_notification_hub"], None),
    ("Notification Hubs namespace", "Microsoft.NotificationHubs/namespaces", "ntfns", ["azurerm_notification_hub_namespace"], None),
    ("Proximity placement group", "Microsoft.Compute/proximityPlacementGroups", "ppg", ["azurerm_proximity_placement_group"], None),
    ("Snapshot", "Microsoft.Compute/snapshots", "snap", ["azurerm_snapshot"], None),
    ("Static web app", "Microsoft.Web/staticSites", "stapp", ["azurerm_static_web_app"], G),
    ("Virtual machine", "Microsoft.Compute/virtualMachines", "vm", ["azurerm_linux_virtual_machine", "azurerm_windows_virtual_machine"], RG),
    ("Virtual machine scale set", "Microsoft.Compute/virtualMachineScaleSets", "vmss", ["azurerm_linux_virtual_machine_scale_set", "azurerm_windows_virtual_machine_scale_set"], None),
    ("Web app", "Microsoft.Web/sites", "app", ["azurerm_linux_web_app", "azurerm_windows_web_app"], G),

    # --- Containers ---
    ("AKS cluster", "Microsoft.ContainerService/managedClusters", "aks", ["azurerm_kubernetes_cluster"], None),
    ("AKS user node pool", "Microsoft.ContainerService/managedClusters/agentPools", "np", ["azurerm_kubernetes_cluster_node_pool"], None),
    ("Container apps", "Microsoft.App/containerApps", "ca", ["azurerm_container_app"], None),
    ("Container apps environment", "Microsoft.App/managedEnvironments", "cae", ["azurerm_container_app_environment"], None),
    ("Container registry", "Microsoft.ContainerRegistry/registries", "cr", ["azurerm_container_registry"], G),
    ("Container instance", "Microsoft.ContainerInstance/containerGroups", "ci", ["azurerm_container_group"], None),
    ("Service Fabric cluster", "Microsoft.ServiceFabric/clusters", "sf", ["azurerm_service_fabric_cluster"], None),

    # --- Databases ---
    ("Azure Cosmos DB database", "Microsoft.DocumentDB/databaseAccounts/sqlDatabases", "cosmos", ["azurerm_cosmosdb_account"], G),
    ("Azure Managed Redis", "Microsoft.Cache/RedisEnterprise", "amr", ["azurerm_redis_enterprise_cluster"], G),
    ("Azure SQL Database server", "Microsoft.Sql/servers", "sql", ["azurerm_mssql_server"], G),
    ("Azure SQL database", "Microsoft.Sql/servers/databases", "sqldb", ["azurerm_mssql_database"], None),
    ("Azure SQL Elastic Pool", "Microsoft.Sql/servers/elasticpool", "sqlep", ["azurerm_mssql_elasticpool"], None),
    ("MySQL database", "Microsoft.DBforMySQL/servers", "mysql", ["azurerm_mysql_flexible_server"], G),
    ("PostgreSQL flexible server", "Microsoft.DBforPostgreSQL/flexibleServers", "pgsql", ["azurerm_postgresql_flexible_server"], G),
    ("SQL Managed Instance", "Microsoft.Sql/managedInstances", "sqlmi", ["azurerm_mssql_managed_instance"], G),

    # --- Developer tools ---
    ("App Configuration store", "Microsoft.AppConfiguration/configurationStores", "appcs", ["azurerm_app_configuration"], G),
    ("Maps account", "Microsoft.Maps/accounts", "map", ["azurerm_maps_account"], None),
    ("SignalR", "Microsoft.SignalRService/SignalR", "sigr", ["azurerm_signalr_service"], G),
    ("WebPubSub", "Microsoft.SignalRService/webPubSub", "wps", ["azurerm_web_pubsub"], G),

    # --- DevOps ---
    ("Azure Managed Grafana", "Microsoft.Dashboard/grafana", "amg", ["azurerm_dashboard_grafana"], None),

    # --- Integration ---
    ("API management service instance", "Microsoft.ApiManagement/service", "apim", ["azurerm_api_management"], G),
    ("Integration account", "Microsoft.Logic/integrationAccounts", "ia", ["azurerm_logic_app_integration_account"], None),
    ("Logic app", "Microsoft.Logic/workflows", "logic", ["azurerm_logic_app_workflow"], None),
    ("Service Bus namespace", "Microsoft.ServiceBus/namespaces", "sbns", ["azurerm_servicebus_namespace"], G),
    ("Service Bus queue", "Microsoft.ServiceBus/namespaces/queues", "sbq", ["azurerm_servicebus_queue"], None),
    ("Service Bus topic", "Microsoft.ServiceBus/namespaces/topics", "sbt", ["azurerm_servicebus_topic"], None),
    ("Service Bus topic subscription", "Microsoft.ServiceBus/namespaces/topics/subscriptions", "sbts", ["azurerm_servicebus_subscription"], None),

    # --- Management and governance ---
    ("Automation account", "Microsoft.Automation/automationAccounts", "aa", ["azurerm_automation_account"], None),
    ("Application Insights", "Microsoft.Insights/components", "appi", ["azurerm_application_insights"], None),
    ("Azure Monitor action group", "Microsoft.Insights/actionGroups", "ag", ["azurerm_monitor_action_group"], None),
    ("Azure Monitor data collection rule", "Microsoft.Insights/dataCollectionRules", "dcr", ["azurerm_monitor_data_collection_rule"], None),
    ("Data collection endpoint", "Microsoft.Insights/dataCollectionEndpoints", "dce", ["azurerm_monitor_data_collection_endpoint"], None),
    ("Log Analytics workspace", "Microsoft.OperationalInsights/workspaces", "log", ["azurerm_log_analytics_workspace"], None),
    ("Log Analytics query packs", "Microsoft.OperationalInsights/querypacks", "pack", ["azurerm_log_analytics_query_pack"], None),
    ("Management group", "Microsoft.Management/managementGroups", "mg", ["azurerm_management_group"], G),
    ("Microsoft Purview instance", "Microsoft.Purview/accounts", "pview", ["azurerm_purview_account"], G),
    ("Resource group", "Microsoft.Resources/resourceGroups", "rg", ["azurerm_resource_group"], None),
    ("Template specs name", "Microsoft.Resources/templateSpecs", "ts", ["azurerm_resource_group_template_deployment"], None),

    # --- Migration ---
    ("Database Migration Service instance", "Microsoft.DataMigration/services", "dms", ["azurerm_database_migration_service"], None),
    ("Recovery Services vault", "Microsoft.RecoveryServices/vaults", "rsv", ["azurerm_recovery_services_vault"], None),

    # --- Networking ---
    ("Application gateway", "Microsoft.Network/applicationGateways", "agw", ["azurerm_application_gateway"], None),
    ("Application security group (ASG)", "Microsoft.Network/applicationSecurityGroups", "asg", ["azurerm_application_security_group"], None),
    ("CDN profile", "Microsoft.Cdn/profiles", "cdnp", ["azurerm_cdn_profile"], None),
    ("CDN endpoint", "Microsoft.Cdn/profiles/endpoints", "cdne", ["azurerm_cdn_endpoint"], None),
    ("Connections", "Microsoft.Network/connections", "con", ["azurerm_virtual_network_gateway_connection"], None),
    ("DNS forwarding ruleset", "Microsoft.Network/dnsForwardingRulesets", "dnsfrs", ["azurerm_private_dns_resolver_dns_forwarding_ruleset"], None),
    ("DNS private resolver", "Microsoft.Network/dnsResolvers", "dnspr", ["azurerm_private_dns_resolver"], None),
    ("Firewall", "Microsoft.Network/azureFirewalls", "afw", ["azurerm_firewall"], None),
    ("Firewall policy", "Microsoft.Network/firewallPolicies", "afwp", ["azurerm_firewall_policy"], None),
    ("ExpressRoute circuit", "Microsoft.Network/expressRouteCircuits", "erc", ["azurerm_express_route_circuit"], None),
    ("ExpressRoute gateway", "Microsoft.Network/virtualNetworkGateways", "ergw", ["azurerm_express_route_gateway"], None),
    ("Front Door (Standard/Premium) profile", "Microsoft.Cdn/profiles", "afd", ["azurerm_cdn_frontdoor_profile"], G),
    ("Front Door (Standard/Premium) endpoint", "Microsoft.Cdn/profiles/afdEndpoints", "fde", ["azurerm_cdn_frontdoor_endpoint"], G),
    ("Front Door firewall policy", "Microsoft.Network/frontdoorWebApplicationFirewallPolicies", "fdfp", ["azurerm_cdn_frontdoor_firewall_policy"], None),
    ("IP group", "Microsoft.Network/ipGroups", "ipg", ["azurerm_ip_group"], None),
    ("Load balancer (internal)", "Microsoft.Network/loadBalancers", "lbi", ["azurerm_lb"], None),
    ("Load balancer (external)", "Microsoft.Network/loadBalancers", "lbe", ["azurerm_lb"], None),
    ("Local network gateway", "Microsoft.Network/localNetworkGateways", "lgw", ["azurerm_local_network_gateway"], None),
    ("NAT gateway", "Microsoft.Network/natGateways", "ng", ["azurerm_nat_gateway"], None),
    ("Network interface (NIC)", "Microsoft.Network/networkInterfaces", "nic", ["azurerm_network_interface"], None),
    ("Network security group (NSG)", "Microsoft.Network/networkSecurityGroups", "nsg", ["azurerm_network_security_group"], None),
    ("Network Watcher", "Microsoft.Network/networkWatchers", "nw", ["azurerm_network_watcher"], None),
    ("Private Link", "Microsoft.Network/privateLinkServices", "pl", ["azurerm_private_link_service"], None),
    ("Private endpoint", "Microsoft.Network/privateEndpoints", "pep", ["azurerm_private_endpoint"], None),
    ("Public IP address", "Microsoft.Network/publicIPAddresses", "pip", ["azurerm_public_ip"], None),
    ("Public IP address prefix", "Microsoft.Network/publicIPPrefixes", "ippre", ["azurerm_public_ip_prefix"], None),
    ("Route filter", "Microsoft.Network/routeFilters", "rf", ["azurerm_route_filter"], None),
    ("Route table", "Microsoft.Network/routeTables", "rt", ["azurerm_route_table"], None),
    ("Traffic Manager profile", "Microsoft.Network/trafficManagerProfiles", "traf", ["azurerm_traffic_manager_profile"], G),
    ("User defined route (UDR)", "Microsoft.Network/routeTables/routes", "udr", ["azurerm_route"], None),
    ("Virtual network", "Microsoft.Network/virtualNetworks", "vnet", ["azurerm_virtual_network"], RG),
    ("Virtual network gateway", "Microsoft.Network/virtualNetworkGateways", "vgw", ["azurerm_virtual_network_gateway"], None),
    ("Virtual network manager", "Microsoft.Network/networkManagers", "vnm", ["azurerm_network_manager"], None),
    ("Virtual network peering", "Microsoft.Network/virtualNetworks/virtualNetworkPeerings", "peer", ["azurerm_virtual_network_peering"], None),
    ("Virtual network subnet", "Microsoft.Network/virtualNetworks/subnets", "snet", ["azurerm_subnet"], None),
    ("Virtual WAN", "Microsoft.Network/virtualWans", "vwan", ["azurerm_virtual_wan"], None),
    ("Virtual WAN Hub", "Microsoft.Network/virtualHubs", "vhub", ["azurerm_virtual_hub"], None),

    # --- Security ---
    ("Azure Bastion", "Microsoft.Network/bastionHosts", "bas", ["azurerm_bastion_host"], None),
    ("Key vault", "Microsoft.KeyVault/vaults", "kv", ["azurerm_key_vault"], G),
    ("Key Vault Managed HSM", "Microsoft.KeyVault/managedHSMs", "kvmhsm", ["azurerm_key_vault_managed_hardware_security_module"], G),
    ("Managed identity", "Microsoft.ManagedIdentity/userAssignedIdentities", "id", ["azurerm_user_assigned_identity"], None),
    ("SSH key", "Microsoft.Compute/sshPublicKeys", "sshkey", ["azurerm_ssh_public_key"], None),
    ("VPN Gateway", "Microsoft.Network/vpnGateways", "vpng", ["azurerm_vpn_gateway"], None),
    ("VPN site", "Microsoft.Network/vpnGateways/vpnSites", "vst", ["azurerm_vpn_site"], None),
    ("Web Application Firewall (WAF) policy", "Microsoft.Network/firewallPolicies", "waf", ["azurerm_web_application_firewall_policy"], None),

    # --- Storage ---
    ("Backup Vault name", "Microsoft.DataProtection/backupVaults", "bvault", ["azurerm_data_protection_backup_vault"], None),
    ("File share", "Microsoft.Storage/storageAccounts/fileServices/shares", "share", ["azurerm_storage_share"], None),
    ("Storage account", "Microsoft.Storage/storageAccounts", "st", ["azurerm_storage_account"], G),
    ("Storage Sync Service name", "Microsoft.StorageSync/storageSyncServices", "sss", ["azurerm_storage_sync"], None),

    # --- Virtual desktop infrastructure ---
    ("Virtual desktop host pool", "Microsoft.DesktopVirtualization/hostPools", "vdpool", ["azurerm_virtual_desktop_host_pool"], None),
    ("Virtual desktop application group", "Microsoft.DesktopVirtualization/applicationGroups", "vdag", ["azurerm_virtual_desktop_application_group"], None),
    ("Virtual desktop workspace", "Microsoft.DesktopVirtualization/workspaces", "vdws", ["azurerm_virtual_desktop_workspace"], None),
    ("Virtual desktop scaling plan", "Microsoft.DesktopVirtualization/scalingPlans", "vdscaling", ["azurerm_virtual_desktop_scaling_plan"], None),
]


def build() -> dict:
    resources = []
    for label, arm, abbr, tf, scope in RESOURCES:
        entry = {
            "label": label,
            "abbreviation": abbr,
            "arm_namespace": arm,
            "terraform_resource_types": tf,
        }
        if scope:
            entry["uniqueness_scope"] = scope
        resources.append(entry)
    return {
        "metadata": SOURCE,
        "component_order": COMPONENT_ORDER,
        "delimiter": DELIMITER,
        "default_code_sets": DEFAULT_CODE_SETS,
        "resources": resources,
    }


def main() -> int:
    catalog = build()
    out = Path(__file__).resolve().parent / "azure-caf.json"
    out.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(catalog['resources'])} resources).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
