[![Build Status](https://travis-ci.org/bwindsor/typed-config-aws-sources.svg?branch=master)](https://travis-ci.org/bwindsor/typed-config-aws-sources)
[![codecov](https://codecov.io/gh/bwindsor/typed-config-aws-sources/branch/master/graph/badge.svg)](https://codecov.io/gh/bwindsor/typed-config-aws-sources)

# typed-config-aws-sources
AWS config sources for the [typed-config](https://pypi.org/project/typed-config) package.

`pip install typed-config-aws-sources`

Requires python 3.6 or above.

## Basic usage
Please read the readme for [typed-config](https://pypi.org/project/typed-config) first.

```python
# my_app/config.py
from typedconfig_awssource import IniS3ConfigSource
from typedconfig import Config, key, section

@section('database')
class AppConfig(Config):
    port = key(cast=int)
    
config = AppConfig()
config.add_source(IniS3ConfigSource('my_bucket_name', 'config_key.cfg'))
config.read()
```

```python
# my_app/main.py
from my_app.config import config
print(config.host)
```

### Supplied Config Sources
#### `IniS3ConfigSource`
This loads configuration from an INI file stored in an S3 bucket
```python
from typedconfig_awssource import IniS3ConfigSource
source = IniS3ConfigSource('bucket_name', 'key_name.cfg', encoding='utf8', must_exist=True)
```

* Supply the bucket name and key name as the first two arguments
* `encoding` defaults to `'utf8'` if not supplied
* `must_exist` defaults to `True` if not supplied. If `must_exist` is `False`, and the bucket or key can't be found, or AWS credentials fail, then no error is thrown and this config source will just return than it cannot find the requested config value every time.

An example INI file might look like this:
```ini
[database]
port = 2000
```

#### `DynamoDBConfigSource`
This reads configuration from a DynamoDB table. The table should have a partition key which holds the config section, a sort key which holds the config key name, and another 'column' containing the config value as a string.

So an item in DynamoDB corresponding to the above INI file example would look like this
```json
{
    "section": "database",
    "key": "port",
    "value": "2000"
}
```

Create the `DynamoDBConfigSource` like this:
```python
from typedconfig_awssource import DynamoDbConfigSource
source = DynamoDbConfigSource('table_name', 
                               section_attribute_name='config_section_column_name',
                               key_attribute_name='config_key_column_name',
                               value_attribute_name='config_value_column_name')
```

* The first argument is the DynamoDB table name and is required
* The other three arguments are optional, and are supplying the attribute (or "column") names in the table which store the three things defining a config parameter (section, key, and value)
* Default attribute names are `"section"`, `"key"`, and `"value"`

#### `SecretsManagerConfigSource`
This reads secret values from secrets manager. Permission to read AWS secrets is required. One secrets should be stored for each config section with the name format `prefix/section`, and contain json key-value pairs. For example, for a project called `myproject` there may be a secret called `myproject/database` containing the following value. Note that even numeric values should be stored as strings.
```json
{
    "user": "secretuser",
    "password": "secretpassword"
}
```

Create the `SecretsManagerConfigSource` like this:
```python
from typedconfig_awssource import SecretsManagerConfigSource
source = SecretsManagerConfigSource('myproject', must_exist=False, only_these_keys={('s', 'a'), ('s', 'b')})
```

* The first argument passed is the prefix which is placed before the `/` in the secret name. So when I try to get the database password, the secret `myproject/database` is retrieved, the JSON is parsed and value the field `password` is returned.  
* The `must_exist` argument specifies whether to error if AWS secretsmanager cannot be accessed, or if the key does not exist. Default is `False`.
* The `only_these_keys` argument specifies a limited set of configuration keys. They are provided as `(section, key)` tuples. If provided, the config source will only act when these parameters are requested. This prevents unnecessary AWS API calls, which slow down configuration setup, for config values which you know are not available from secrets manager. Setting `only_these_keys=None` (the default) will check secrets manager for all config keys.

#### `ParameterStoreConfigSource`
This reads (optionally secret) values from AWS SSM parameter store. Storing secrets here is cheaper than using secrets manager. Permission to read from SSM parameter store is required. Each config parameter should be stored in parameter store as an individual `SecureString` parameter. For example, I would store the database password in a key called
```
myproject/database/password
```
where `database` is the section name and `password` is the configuration key name.

Create a `ParameterStoreConfigSource` like this:
```python
from typedconfig_awssource import ParameterStoreConfigSource
source = ParameterStoreConfigSource('myproject', must_exist=False, only_these_keys={('s', 'a'), ('s', 'b')})
```

* The first argument passed is the prefix at the start of the SSM parameter name, before the first `/`.
* The `must_exist` argument specifies whether to error if AWS parameter store cannot be accessed, or if the requested key does not exist.
* The `only_these_keys` argument specifies a limited set of configuration keys. They are provided as `(section, key)` tuples. If provided, the config source will only act when these parameters are requested. This prevents unnecessary AWS API calls, which slow down configuration setup, for config values which you know are not available from parameter store. Setting `only_these_keys=None` (the default) will check parameter store for all config keys.

## Contributing
Ideas for new features and pull requests are welcome. PRs must come with tests included. This was developed using Python 3.7 but Travis tests run with v3.6 too.

### Development setup
1. Clone the git repository
2. Create a virtual environment `virtualenv venv`
3. Activate the environment `venv/scripts/activate`
4. Install development dependencies `pip install -r requirements.txt`

### Running tests
`pytest`

To run with coverage:

`pytest --cov`

### Making a release
1. Bump version number in `typedconfig_awssource/__version__.py`
1. Add changes to [CHANGELOG.md](CHANGELOG.md)
1. Commit your changes and tag with `git tag -a 0.1.0 -m "Summary of changes"`
1. Travis will deploy the release to PyPi for you.

#### Staging release
If you want to check how a release will look on PyPi before tagging and making it live, you can do the following:
1. `pip install twine` if you don't already have it
1. Bump version number in `typedconfig_awssource/__version__.py`
1. Clear the dist directory `rm -r dist`
1. `python setup.py sdist bdist_wheel`
1. `twine check dist/*`
1. Upload to the test PyPI `twine upload --repository-url https://test.pypi.org/legacy/ dist/*`
1. Check all looks ok at [https://test.pypi.org/project/typed-config-aws-sources](https://test.pypi.org/project/typed-config-aws-sources)
1. If all looks good you can git tag and push for deploy to live PyPi

Here is [a good tutorial](https://realpython.com/pypi-publish-python-package) on publishing packages to PyPI.
