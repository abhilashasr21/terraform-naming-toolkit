# Naming Workbook Conversion Report

- Source workbook: `(none - CAF baseline)`
- Source SHA-256: `1a444a018934a932b0096f519283ebd9f40e37a142bd3ea5b8c10a45d5d653c7`
- Code sets: environment
- Rules generated: 156
- Approved (enforced) rules: 156
- Rules using CAF fallback: 156

## Rules

| Rule | Resource | Status | TF mapped | CAF | Source pattern | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `ai_search` | AI Search | approved | yes | yes | `srch-<workload>-<environment>-<region>-<instance>` |  |
| `aks_cluster` | AKS cluster | approved | yes | yes | `aks-<workload>-<environment>-<region>-<instance>` |  |
| `aks_user_node_pool` | AKS user node pool | approved | yes | yes | `np-<workload>-<environment>-<region>-<instance>` |  |
| `api_management_service_instance` | API management service instance | approved | yes | yes | `apim-<workload>-<environment>-<region>-<instance>` |  |
| `app_configuration_store` | App Configuration store | approved | yes | yes | `appcs-<workload>-<environment>-<region>-<instance>` |  |
| `app_service_environment` | App Service environment | approved | yes | yes | `ase-<workload>-<environment>-<region>-<instance>` |  |
| `app_service_plan` | App Service plan | approved | yes | yes | `asp-<workload>-<environment>-<region>-<instance>` |  |
| `application_gateway` | Application gateway | approved | yes | yes | `agw-<workload>-<environment>-<region>-<instance>` |  |
| `application_insights` | Application Insights | approved | yes | yes | `appi-<workload>-<environment>-<region>-<instance>` |  |
| `application_security_group` | Application security group (ASG) | approved | yes | yes | `asg-<workload>-<environment>-<region>-<instance>` |  |
| `automation_account` | Automation account | approved | yes | yes | `aa-<workload>-<environment>-<region>-<instance>` |  |
| `availability_set` | Availability set | approved | yes | yes | `avail-<workload>-<environment>-<region>-<instance>` |  |
| `azure_ai_video_indexer` | Azure AI Video Indexer | approved | no | yes | `avi-<workload>-<environment>-<region>-<instance>` |  |
| `azure_analysis_services_server` | Azure Analysis Services server | approved | yes | yes | `as-<workload>-<environment>-<region>-<instance>` |  |
| `azure_arc_enabled_kubernetes_cluster` | Azure Arc enabled Kubernetes cluster | approved | no | yes | `arck-<workload>-<environment>-<region>-<instance>` |  |
| `azure_arc_enabled_server` | Azure Arc enabled server | approved | no | yes | `arcs-<workload>-<environment>-<region>-<instance>` |  |
| `azure_bastion` | Azure Bastion | approved | yes | yes | `bas-<workload>-<environment>-<region>-<instance>` |  |
| `azure_cosmos_db_database` | Azure Cosmos DB database | approved | yes | yes | `cosmos-<workload>-<environment>-<region>-<instance>` |  |
| `azure_data_explorer_cluster` | Azure Data Explorer cluster | approved | yes | yes | `dec-<workload>-<environment>-<region>-<instance>` |  |
| `azure_data_explorer_cluster_database` | Azure Data Explorer cluster database | approved | yes | yes | `dedb-<workload>-<environment>-<region>-<instance>` |  |
| `azure_data_factory` | Azure Data Factory | approved | yes | yes | `adf-<workload>-<environment>-<region>-<instance>` |  |
| `azure_databricks_workspace` | Azure Databricks workspace | approved | yes | yes | `dbw-<workload>-<environment>-<region>-<instance>` |  |
| `azure_digital_twin_instance` | Azure Digital Twin instance | approved | yes | yes | `dt-<workload>-<environment>-<region>-<instance>` |  |
| `azure_load_testing_instance` | Azure Load Testing instance | approved | yes | yes | `lt-<workload>-<environment>-<region>-<instance>` |  |
| `azure_machine_learning_workspace` | Azure Machine Learning workspace | approved | yes | yes | `mlw-<workload>-<environment>-<region>-<instance>` |  |
| `azure_managed_grafana` | Azure Managed Grafana | approved | yes | yes | `amg-<workload>-<environment>-<region>-<instance>` |  |
| `azure_managed_redis` | Azure Managed Redis | approved | yes | yes | `amr-<workload>-<environment>-<region>-<instance>` |  |
| `azure_monitor_action_group` | Azure Monitor action group | approved | yes | yes | `ag-<workload>-<environment>-<region>-<instance>` |  |
| `azure_monitor_data_collection_rule` | Azure Monitor data collection rule | approved | yes | yes | `dcr-<workload>-<environment>-<region>-<instance>` |  |
| `azure_openai_service` | Azure OpenAI Service | approved | no | yes | `oai-<workload>-<environment>-<region>-<instance>` |  |
| `azure_sql_database` | Azure SQL database | approved | yes | yes | `sqldb-<workload>-<environment>-<region>-<instance>` |  |
| `azure_sql_database_server` | Azure SQL Database server | approved | yes | yes | `sql-<workload>-<environment>-<region>-<instance>` |  |
| `azure_sql_elastic_pool` | Azure SQL Elastic Pool | approved | yes | yes | `sqlep-<workload>-<environment>-<region>-<instance>` |  |
| `azure_stream_analytics` | Azure Stream Analytics | approved | yes | yes | `asa-<workload>-<environment>-<region>-<instance>` |  |
| `azure_synapse_analytics_spark_pool` | Azure Synapse Analytics Spark Pool | approved | yes | yes | `synsp-<workload>-<environment>-<region>-<instance>` |  |
| `azure_synapse_analytics_sql_dedicated_pool` | Azure Synapse Analytics SQL Dedicated Pool | approved | yes | yes | `syndp-<workload>-<environment>-<region>-<instance>` |  |
| `azure_synapse_analytics_workspaces` | Azure Synapse Analytics workspaces | approved | yes | yes | `synw-<workload>-<environment>-<region>-<instance>` |  |
| `backup_vault_name` | Backup Vault name | approved | yes | yes | `bvault-<workload>-<environment>-<region>-<instance>` |  |
| `batch_accounts` | Batch accounts | approved | yes | yes | `ba-<workload>-<environment>-<region>-<instance>` |  |
| `bot_service` | Bot service | approved | yes | yes | `bot-<workload>-<environment>-<region>-<instance>` |  |
| `cdn_endpoint` | CDN endpoint | approved | yes | yes | `cdne-<workload>-<environment>-<region>-<instance>` |  |
| `cdn_profile` | CDN profile | approved | yes | yes | `cdnp-<workload>-<environment>-<region>-<instance>` |  |
| `communication_services` | Communication Services | approved | yes | yes | `acs-<workload>-<environment>-<region>-<instance>` |  |
| `computer_vision` | Computer vision | approved | no | yes | `cv-<workload>-<environment>-<region>-<instance>` |  |
| `connections` | Connections | approved | yes | yes | `con-<workload>-<environment>-<region>-<instance>` |  |
| `container_apps` | Container apps | approved | yes | yes | `ca-<workload>-<environment>-<region>-<instance>` |  |
| `container_apps_environment` | Container apps environment | approved | yes | yes | `cae-<workload>-<environment>-<region>-<instance>` |  |
| `container_instance` | Container instance | approved | yes | yes | `ci-<workload>-<environment>-<region>-<instance>` |  |
| `container_registry` | Container registry | approved | yes | yes | `cr-<workload>-<environment>-<region>-<instance>` |  |
| `content_moderator` | Content moderator | approved | no | yes | `cm-<workload>-<environment>-<region>-<instance>` |  |
| `content_safety` | Content safety | approved | no | yes | `cs-<workload>-<environment>-<region>-<instance>` |  |
| `data_collection_endpoint` | Data collection endpoint | approved | yes | yes | `dce-<workload>-<environment>-<region>-<instance>` |  |
| `data_lake_store_account` | Data Lake Store account | approved | yes | yes | `dls-<workload>-<environment>-<region>-<instance>` |  |
| `database_migration_service_instance` | Database Migration Service instance | approved | yes | yes | `dms-<workload>-<environment>-<region>-<instance>` |  |
| `disk_encryption_set` | Disk encryption set | approved | yes | yes | `des-<workload>-<environment>-<region>-<instance>` |  |
| `dns_forwarding_ruleset` | DNS forwarding ruleset | approved | yes | yes | `dnsfrs-<workload>-<environment>-<region>-<instance>` |  |
| `dns_private_resolver` | DNS private resolver | approved | yes | yes | `dnspr-<workload>-<environment>-<region>-<instance>` |  |
| `document_intelligence` | Document intelligence | approved | no | yes | `di-<workload>-<environment>-<region>-<instance>` |  |
| `event_grid_domain` | Event Grid domain | approved | yes | yes | `evgd-<workload>-<environment>-<region>-<instance>` |  |
| `event_grid_subscriptions` | Event Grid subscriptions | approved | yes | yes | `evgs-<workload>-<environment>-<region>-<instance>` |  |
| `event_grid_system_topic` | Event Grid system topic | approved | yes | yes | `egst-<workload>-<environment>-<region>-<instance>` |  |
| `event_grid_topic` | Event Grid topic | approved | yes | yes | `evgt-<workload>-<environment>-<region>-<instance>` |  |
| `event_hub` | Event hub | approved | yes | yes | `evh-<workload>-<environment>-<region>-<instance>` |  |
| `event_hub_consumer_group` | Event hub consumer group | approved | yes | yes | `evhcg-<workload>-<environment>-<region>-<instance>` |  |
| `event_hubs_namespace` | Event Hubs namespace | approved | yes | yes | `evhns-<workload>-<environment>-<region>-<instance>` |  |
| `expressroute_circuit` | ExpressRoute circuit | approved | yes | yes | `erc-<workload>-<environment>-<region>-<instance>` |  |
| `expressroute_gateway` | ExpressRoute gateway | approved | yes | yes | `ergw-<workload>-<environment>-<region>-<instance>` |  |
| `face_api` | Face API | approved | no | yes | `face-<workload>-<environment>-<region>-<instance>` |  |
| `file_share` | File share | approved | yes | yes | `share-<workload>-<environment>-<region>-<instance>` |  |
| `firewall` | Firewall | approved | yes | yes | `afw-<workload>-<environment>-<region>-<instance>` |  |
| `firewall_policy` | Firewall policy | approved | yes | yes | `afwp-<workload>-<environment>-<region>-<instance>` |  |
| `foundry_account` | Foundry account | approved | no | yes | `aif-<workload>-<environment>-<region>-<instance>` |  |
| `foundry_hub` | Foundry hub | approved | no | yes | `hub-<workload>-<environment>-<region>-<instance>` |  |
| `foundry_tools` | Foundry Tools (multi-service account) | approved | yes | yes | `ais-<workload>-<environment>-<region>-<instance>` |  |
| `front_door_endpoint` | Front Door (Standard/Premium) endpoint | approved | yes | yes | `fde-<workload>-<environment>-<region>-<instance>` |  |
| `front_door_firewall_policy` | Front Door firewall policy | approved | yes | yes | `fdfp-<workload>-<environment>-<region>-<instance>` |  |
| `front_door_profile` | Front Door (Standard/Premium) profile | approved | yes | yes | `afd-<workload>-<environment>-<region>-<instance>` |  |
| `function_app` | Function app | approved | yes | yes | `func-<workload>-<environment>-<region>-<instance>` |  |
| `gallery` | Gallery | approved | yes | yes | `gal-<workload>-<environment>-<region>-<instance>` |  |
| `hdinsight_hadoop_cluster` | HDInsight - Hadoop cluster | approved | yes | yes | `hadoop-<workload>-<environment>-<region>-<instance>` |  |
| `hdinsight_hbase_cluster` | HDInsight - HBase cluster | approved | yes | yes | `hbase-<workload>-<environment>-<region>-<instance>` |  |
| `hdinsight_kafka_cluster` | HDInsight - Kafka cluster | approved | yes | yes | `kafka-<workload>-<environment>-<region>-<instance>` |  |
| `hdinsight_spark_cluster` | HDInsight - Spark cluster | approved | yes | yes | `spark-<workload>-<environment>-<region>-<instance>` |  |
| `health_insights` | Health Insights | approved | no | yes | `hi-<workload>-<environment>-<region>-<instance>` |  |
| `immersive_reader` | Immersive reader | approved | no | yes | `ir-<workload>-<environment>-<region>-<instance>` |  |
| `integration_account` | Integration account | approved | yes | yes | `ia-<workload>-<environment>-<region>-<instance>` |  |
| `iot_hub` | IoT hub | approved | yes | yes | `iot-<workload>-<environment>-<region>-<instance>` |  |
| `ip_group` | IP group | approved | yes | yes | `ipg-<workload>-<environment>-<region>-<instance>` |  |
| `key_vault` | Key vault | approved | yes | yes | `kv-<workload>-<environment>-<region>-<instance>` |  |
| `key_vault_managed_hsm` | Key Vault Managed HSM | approved | yes | yes | `kvmhsm-<workload>-<environment>-<region>-<instance>` |  |
| `language_service` | Language service | approved | no | yes | `lang-<workload>-<environment>-<region>-<instance>` |  |
| `load_balancer` | Load balancer (internal) | approved | yes | yes | `lbi-<workload>-<environment>-<region>-<instance>` |  |
| `local_network_gateway` | Local network gateway | approved | yes | yes | `lgw-<workload>-<environment>-<region>-<instance>` |  |
| `log_analytics_query_packs` | Log Analytics query packs | approved | yes | yes | `pack-<workload>-<environment>-<region>-<instance>` |  |
| `log_analytics_workspace` | Log Analytics workspace | approved | yes | yes | `log-<workload>-<environment>-<region>-<instance>` |  |
| `logic_app` | Logic app | approved | yes | yes | `logic-<workload>-<environment>-<region>-<instance>` |  |
| `managed_disk` | Managed disk (data) | approved | yes | yes | `disk-<workload>-<environment>-<region>-<instance>` |  |
| `managed_identity` | Managed identity | approved | yes | yes | `id-<workload>-<environment>-<region>-<instance>` |  |
| `management_group` | Management group | approved | yes | yes | `mg-<workload>-<environment>-<region>-<instance>` |  |
| `maps_account` | Maps account | approved | yes | yes | `map-<workload>-<environment>-<region>-<instance>` |  |
| `microsoft_purview_instance` | Microsoft Purview instance | approved | yes | yes | `pview-<workload>-<environment>-<region>-<instance>` |  |
| `mysql_database` | MySQL database | approved | yes | yes | `mysql-<workload>-<environment>-<region>-<instance>` |  |
| `nat_gateway` | NAT gateway | approved | yes | yes | `ng-<workload>-<environment>-<region>-<instance>` |  |
| `network_interface` | Network interface (NIC) | approved | yes | yes | `nic-<workload>-<environment>-<region>-<instance>` |  |
| `network_security_group` | Network security group (NSG) | approved | yes | yes | `nsg-<workload>-<environment>-<region>-<instance>` |  |
| `network_watcher` | Network Watcher | approved | yes | yes | `nw-<workload>-<environment>-<region>-<instance>` |  |
| `notification_hubs` | Notification Hubs | approved | yes | yes | `ntf-<workload>-<environment>-<region>-<instance>` |  |
| `notification_hubs_namespace` | Notification Hubs namespace | approved | yes | yes | `ntfns-<workload>-<environment>-<region>-<instance>` |  |
| `postgresql_flexible_server` | PostgreSQL flexible server | approved | yes | yes | `pgsql-<workload>-<environment>-<region>-<instance>` |  |
| `power_bi_embedded` | Power BI Embedded | approved | yes | yes | `pbi-<workload>-<environment>-<region>-<instance>` |  |
| `private_endpoint` | Private endpoint | approved | yes | yes | `pep-<workload>-<environment>-<region>-<instance>` |  |
| `private_link` | Private Link | approved | yes | yes | `pl-<workload>-<environment>-<region>-<instance>` |  |
| `provisioning_services` | Provisioning services | approved | yes | yes | `provs-<workload>-<environment>-<region>-<instance>` |  |
| `proximity_placement_group` | Proximity placement group | approved | yes | yes | `ppg-<workload>-<environment>-<region>-<instance>` |  |
| `public_ip_address` | Public IP address | approved | yes | yes | `pip-<workload>-<environment>-<region>-<instance>` |  |
| `public_ip_address_prefix` | Public IP address prefix | approved | yes | yes | `ippre-<workload>-<environment>-<region>-<instance>` |  |
| `recovery_services_vault` | Recovery Services vault | approved | yes | yes | `rsv-<workload>-<environment>-<region>-<instance>` |  |
| `resource_group` | Resource group | approved | yes | yes | `rg-<workload>-<environment>-<region>-<instance>` |  |
| `route_filter` | Route filter | approved | yes | yes | `rf-<workload>-<environment>-<region>-<instance>` |  |
| `route_table` | Route table | approved | yes | yes | `rt-<workload>-<environment>-<region>-<instance>` |  |
| `service_bus_namespace` | Service Bus namespace | approved | yes | yes | `sbns-<workload>-<environment>-<region>-<instance>` |  |
| `service_bus_queue` | Service Bus queue | approved | yes | yes | `sbq-<workload>-<environment>-<region>-<instance>` |  |
| `service_bus_topic` | Service Bus topic | approved | yes | yes | `sbt-<workload>-<environment>-<region>-<instance>` |  |
| `service_bus_topic_subscription` | Service Bus topic subscription | approved | yes | yes | `sbts-<workload>-<environment>-<region>-<instance>` |  |
| `service_fabric_cluster` | Service Fabric cluster | approved | yes | yes | `sf-<workload>-<environment>-<region>-<instance>` |  |
| `signalr` | SignalR | approved | yes | yes | `sigr-<workload>-<environment>-<region>-<instance>` |  |
| `snapshot` | Snapshot | approved | yes | yes | `snap-<workload>-<environment>-<region>-<instance>` |  |
| `speech_service` | Speech service | approved | no | yes | `spch-<workload>-<environment>-<region>-<instance>` |  |
| `sql_managed_instance` | SQL Managed Instance | approved | yes | yes | `sqlmi-<workload>-<environment>-<region>-<instance>` |  |
| `ssh_key` | SSH key | approved | yes | yes | `sshkey-<workload>-<environment>-<region>-<instance>` |  |
| `static_web_app` | Static web app | approved | yes | yes | `stapp-<workload>-<environment>-<region>-<instance>` |  |
| `storage_account` | Storage account | approved | yes | yes | `st-<workload>-<environment>-<region>-<instance>` |  |
| `storage_sync_service_name` | Storage Sync Service name | approved | yes | yes | `sss-<workload>-<environment>-<region>-<instance>` |  |
| `template_specs_name` | Template specs name | approved | yes | yes | `ts-<workload>-<environment>-<region>-<instance>` |  |
| `time_series_insights_environment` | Time Series Insights environment | approved | yes | yes | `tsi-<workload>-<environment>-<region>-<instance>` |  |
| `traffic_manager_profile` | Traffic Manager profile | approved | yes | yes | `traf-<workload>-<environment>-<region>-<instance>` |  |
| `translator` | Translator | approved | no | yes | `trsl-<workload>-<environment>-<region>-<instance>` |  |
| `user_defined_route` | User defined route (UDR) | approved | yes | yes | `udr-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_desktop_application_group` | Virtual desktop application group | approved | yes | yes | `vdag-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_desktop_host_pool` | Virtual desktop host pool | approved | yes | yes | `vdpool-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_desktop_scaling_plan` | Virtual desktop scaling plan | approved | yes | yes | `vdscaling-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_desktop_workspace` | Virtual desktop workspace | approved | yes | yes | `vdws-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_machine` | Virtual machine | approved | yes | yes | `vm-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_machine_scale_set` | Virtual machine scale set | approved | yes | yes | `vmss-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_network` | Virtual network | approved | yes | yes | `vnet-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_network_gateway` | Virtual network gateway | approved | yes | yes | `vgw-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_network_manager` | Virtual network manager | approved | yes | yes | `vnm-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_network_peering` | Virtual network peering | approved | yes | yes | `peer-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_network_subnet` | Virtual network subnet | approved | yes | yes | `snet-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_wan` | Virtual WAN | approved | yes | yes | `vwan-<workload>-<environment>-<region>-<instance>` |  |
| `virtual_wan_hub` | Virtual WAN Hub | approved | yes | yes | `vhub-<workload>-<environment>-<region>-<instance>` |  |
| `vpn_gateway` | VPN Gateway | approved | yes | yes | `vpng-<workload>-<environment>-<region>-<instance>` |  |
| `vpn_site` | VPN site | approved | yes | yes | `vst-<workload>-<environment>-<region>-<instance>` |  |
| `web_app` | Web app | approved | yes | yes | `app-<workload>-<environment>-<region>-<instance>` |  |
| `web_application_firewall_policy` | Web Application Firewall (WAF) policy | approved | yes | yes | `waf-<workload>-<environment>-<region>-<instance>` |  |
| `webpubsub` | WebPubSub | approved | yes | yes | `wps-<workload>-<environment>-<region>-<instance>` |  |

Only `approved` rules are enforced by the engine. Review `draft`, `conflict`, and `missing` rows with the customer before promoting them.
