#!/usr/bin/env python3

# 成本控制脚本
# 用于监控资源使用情况，避免超支

import os
import sys
import json
import logging
import requests
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cost-control')

# 配置
CONFIG = {
    'aws': {
        'enabled': False,
        'access_key': os.environ.get('AWS_ACCESS_KEY_ID'),
        'secret_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
        'region': 'us-east-1',
        'budget_threshold': 80.0,  # 预算阈值百分比
        'max_ec2_instances': 2,
        'max_s3_storage_gb': 5
    },
    'gcp': {
        'enabled': False,
        'service_account_key': os.environ.get('GCP_SERVICE_ACCOUNT_KEY'),
        'project_id': os.environ.get('GCP_PROJECT_ID'),
        'budget_threshold': 80.0,  # 预算阈值百分比
        'max_compute_instances': 2,
        'max_storage_gb': 5
    },
    'local': {
        'enabled': True,
        'docker_compose_path': './docker-compose.yml',
        'monitor_interval': 60,  # 监控间隔（秒）
        'max_containers': 10
    }
}

class CostControl:
    def __init__(self):
        self.aws_enabled = CONFIG['aws']['enabled']
        self.gcp_enabled = CONFIG['gcp']['enabled']
        self.local_enabled = CONFIG['local']['enabled']
    
    def check_local_resources(self):
        """检查本地Docker资源使用情况"""
        if not self.local_enabled:
            logger.info("Local resource monitoring disabled")
            return
        
        logger.info("Checking local Docker resources...")
        
        try:
            # 检查运行中的容器数量
            import subprocess
            result = subprocess.run(['docker', 'ps', '-q'], capture_output=True, text=True)
            containers = result.stdout.strip().split('\n')
            container_count = len([c for c in containers if c])
            
            logger.info(f"Running containers: {container_count}")
            
            if container_count > CONFIG['local']['max_containers']:
                logger.warning(f"Container count ({container_count}) exceeds maximum ({CONFIG['local']['max_containers']})")
                # 可以在这里添加自动停止空闲容器的逻辑
        except Exception as e:
            logger.error(f"Error checking local resources: {str(e)}")
    
    def check_aws_costs(self):
        """检查AWS成本和资源使用情况"""
        if not self.aws_enabled:
            logger.info("AWS cost monitoring disabled")
            return
        
        logger.info("Checking AWS costs...")
        
        try:
            # 这里应该使用boto3库来检查AWS成本
            # 由于boto3需要额外安装，这里只提供示例代码框架
            import boto3
            
            # 检查EC2实例数量
            ec2 = boto3.client('ec2', region_name=CONFIG['aws']['region'])
            instances = ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
            instance_count = sum(len(reservation['Instances']) for reservation in instances['Reservations'])
            
            logger.info(f"Running EC2 instances: {instance_count}")
            
            if instance_count > CONFIG['aws']['max_ec2_instances']:
                logger.warning(f"EC2 instance count ({instance_count}) exceeds maximum ({CONFIG['aws']['max_ec2_instances']})")
            
            # 检查S3存储使用情况
            s3 = boto3.client('s3')
            buckets = s3.list_buckets()['Buckets']
            total_storage = 0
            
            for bucket in buckets:
                bucket_name = bucket['Name']
                try:
                    response = s3.list_objects_v2(Bucket=bucket_name)
                    if 'Contents' in response:
                        bucket_size = sum(obj['Size'] for obj in response['Contents'])
                        total_storage += bucket_size
                except Exception as e:
                    logger.error(f"Error checking S3 bucket {bucket_name}: {str(e)}")
            
            total_storage_gb = total_storage / (1024 ** 3)
            logger.info(f"Total S3 storage: {total_storage_gb:.2f} GB")
            
            if total_storage_gb > CONFIG['aws']['max_s3_storage_gb']:
                logger.warning(f"S3 storage ({total_storage_gb:.2f} GB) exceeds maximum ({CONFIG['aws']['max_s3_storage_gb']} GB)")
            
        except ImportError:
            logger.warning("boto3 not installed, skipping AWS cost check")
        except Exception as e:
            logger.error(f"Error checking AWS costs: {str(e)}")
    
    def check_gcp_costs(self):
        """检查GCP成本和资源使用情况"""
        if not self.gcp_enabled:
            logger.info("GCP cost monitoring disabled")
            return
        
        logger.info("Checking GCP costs...")
        
        try:
            # 这里应该使用google-cloud库来检查GCP成本
            # 由于google-cloud需要额外安装，这里只提供示例代码框架
            from google.cloud import compute_v1
            from google.cloud import storage
            
            # 检查Compute Engine实例数量
            compute_client = compute_v1.InstancesClient()
            instances = compute_client.list(project=CONFIG['gcp']['project_id'], zone='us-central1-a')
            instance_count = sum(1 for _ in instances)
            
            logger.info(f"Running Compute Engine instances: {instance_count}")
            
            if instance_count > CONFIG['gcp']['max_compute_instances']:
                logger.warning(f"Compute Engine instance count ({instance_count}) exceeds maximum ({CONFIG['gcp']['max_compute_instances']})")
            
            # 检查Cloud Storage使用情况
            storage_client = storage.Client(project=CONFIG['gcp']['project_id'])
            buckets = storage_client.list_buckets()
            total_storage = 0
            
            for bucket in buckets:
                blobs = storage_client.list_blobs(bucket.name)
                bucket_size = sum(blob.size for blob in blobs)
                total_storage += bucket_size
            
            total_storage_gb = total_storage / (1024 ** 3)
            logger.info(f"Total Cloud Storage: {total_storage_gb:.2f} GB")
            
            if total_storage_gb > CONFIG['gcp']['max_storage_gb']:
                logger.warning(f"Cloud Storage ({total_storage_gb:.2f} GB) exceeds maximum ({CONFIG['gcp']['max_storage_gb']} GB)")
            
        except ImportError:
            logger.warning("google-cloud not installed, skipping GCP cost check")
        except Exception as e:
            logger.error(f"Error checking GCP costs: {str(e)}")
    
    def send_alert(self, message):
        """发送成本告警"""
        logger.warning(f"ALERT: {message}")
        
        # 这里可以添加发送邮件、Slack通知等逻辑
        # 例如，使用SMTP发送邮件
        # import smtplib
        # from email.mime.text import MIMEText
        # 
        # msg = MIMEText(message)
        # msg['Subject'] = 'Cost Control Alert'
        # msg['From'] = 'alerts@example.com'
        # msg['To'] = 'admin@example.com'
        # 
        # with smtplib.SMTP('smtp.example.com') as server:
        #     server.login('username', 'password')
        #     server.send_message(msg)
    
    def run(self):
        """运行所有成本控制检查"""
        logger.info("Running cost control checks...")
        
        self.check_local_resources()
        self.check_aws_costs()
        self.check_gcp_costs()
        
        logger.info("Cost control checks completed")

if __name__ == "__main__":
    cost_control = CostControl()
    cost_control.run()