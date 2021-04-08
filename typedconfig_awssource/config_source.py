"""
Module containing AWS dependent configuration sources
"""
import boto3
import json
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, Dict, Set, Tuple
from typedconfig.config import ConfigSource
from typedconfig.source import AbstractIniConfigSource
from configparser import ConfigParser


class DynamoDbConfigSource(ConfigSource):
    def __init__(self, table_name: str,
                 section_attribute_name: str='section',
                 key_attribute_name: str='key',
                 value_attribute_name: str='value'):
        self.table_name = table_name
        self.section_attribute_name = section_attribute_name
        self.key_attribute_name = key_attribute_name
        self.value_attribute_name = value_attribute_name
        self._client = boto3.client('dynamodb')

    def get_config_value(self, section_name: str, key_name: str) -> Optional[str]:
        response = self._client.get_item(
            TableName=self.table_name,
            Key={
                self.section_attribute_name: {
                    'S': section_name.lower()
                },
                self.key_attribute_name: {
                    'S': key_name.lower()
                }
            }
        )
        if 'Item' not in response:
            return None

        # Not this will error is the appropriate field are not found
        # inside 'Item'. This is expected behaviour since the table
        # has been set up wrongly if these things aren't present
        return response['Item'][self.value_attribute_name]['S']


class IniS3ConfigSource(AbstractIniConfigSource):
    def __init__(self, bucket: str, key: str, encoding: str='utf-8', must_exist=True):
        config = ConfigParser()

        try:
            s3 = boto3.resource('s3')
            obj = s3.Object(bucket, key)
            byte_string = obj.get()['Body'].read()
            decoded_string = byte_string.decode(encoding)
            config.read_string(decoded_string)
        except (ClientError, NoCredentialsError):
            if must_exist:
                raise
        super().__init__(config)

    def get_config_value(self, section_name: str, key_name: str) -> Optional[str]:
        return super().get_config_value(section_name.lower(), key_name.lower())


class SecretsManagerConfigSource(ConfigSource):
    def __init__(self, secret_name_prefix: str, must_exist: bool=False,
                 only_these_keys: Optional[Set[Tuple[str, str]]]=None):
        assert type(secret_name_prefix) is str
        assert len(secret_name_prefix) > 0
        # Create a Secrets Manager client
        self._client = boto3.client('secretsmanager')
        self._secret_name_prefix = secret_name_prefix
        self._must_exist = must_exist
        self._only_these_keys = {(s.lower(), k.lower()) for s, k in only_these_keys} if only_these_keys is not None else None

    def get_config_value(self, section_name: str, key_name: str) -> Optional[str]:
        if self._only_these_keys is not None:
            if (section_name.lower(), key_name.lower()) not in self._only_these_keys:
                return None

        secret_name = self._secret_name_prefix + "/" + section_name.lower()
        try:
            response = self._client.get_secret_value(SecretId=secret_name)
        except (NoCredentialsError, ClientError):
            if self._must_exist:
                raise
            else:
                return None
        except self._client.exceptions.ResourceNotFoundException:
            return None

        section_contents: Dict[str, str] = json.loads(response['SecretString'])

        # Make all keys lowercase
        section_contents = {k.lower(): v for k, v in section_contents.items()}

        value = section_contents.get(key_name.lower(), None)
        if value is None and self._must_exist:
            raise KeyError("Config section {0} was found but key {1} was not found within it.".format(section_name, key_name))

        return value


class ParameterStoreConfigSource(ConfigSource):
    def __init__(self,
                 parameter_name_prefix: str,
                 must_exist: bool = False,
                 only_these_keys: Optional[Set[Tuple[str, str]]] = None,
                 batch_preload: bool = False):
        assert type(parameter_name_prefix) is str
        assert len(parameter_name_prefix) > 0
        # Create a Secrets Manager client
        self._client = boto3.client('ssm')
        self._parameter_name_prefix = parameter_name_prefix
        self._must_exist = must_exist
        self._only_these_keys = {(s.lower(), k.lower()) for s, k in only_these_keys} if only_these_keys is not None else None

        self._preload = dict()
        if self._only_these_keys is not None and len(self._only_these_keys) > 0 and batch_preload is True:
            response = self._client.get_parameters(
                Names=[
                    self._make_parameter_name(section_name, key_name)
                    for section_name, key_name in self._only_these_keys
                ],
                WithDecryption=True,
            )
            if len(response['InvalidParameters']) > 0 and self._must_exist:
                raise KeyError("Could not find parameters: " + ", ".join(response['InvalidParameters']))
            self._preload = {
                parameter['Name']: parameter['Value']
                for parameter in response['Parameters']
            }

    def _make_parameter_name(self, section_name: str, key_name: str):
        return self._parameter_name_prefix + "/" + section_name.lower() + "/" + key_name.lower()

    def get_config_value(self, section_name: str, key_name: str) -> Optional[str]:
        if self._only_these_keys is not None:
            if (section_name.lower(), key_name.lower()) not in self._only_these_keys:
                return None

        parameter_name = self._make_parameter_name(section_name, key_name)
        if parameter_name in self._preload:
            return self._preload[parameter_name]

        try:
            response = self._client.get_parameter(
                Name=parameter_name,
                WithDecryption=True
            )
        except (NoCredentialsError, ClientError):
            if self._must_exist:
                raise
            else:
                return None
        except self._client.exceptions.ResourceNotFoundException:
            return None

        return response['Parameter']['Value']
