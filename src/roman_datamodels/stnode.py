"""
Proof of concept of using tags with the data model framework
"""

import jsonschema
from asdf.extension import Converter
from collections import UserList
from .stuserdict import STUserDict as UserDict
import asdf
import asdf.schema as asdfschema
import asdf.yamlutil as yamlutil
from asdf.util import HashableDict
#from .properties import _get_schema_for_property
from .validate import _check_type, _error_message

validate = True
strict_validation = True

def set_validate(value):
    global validate
    validate = bool(value)


validator_callbacks = HashableDict(asdfschema.YAML_VALIDATORS)
validator_callbacks.update({'type': _check_type})


def _value_change(path, value, schema, pass_invalid_values,
                 strict_validation, ctx):
    """
    Validate a change in value against a schema.
    Trap error and return a flag.
    """
    try:
        _check_value(value, schema, ctx)
        update = True

    except jsonschema.ValidationError as error:
        update = False
        errmsg = _error_message(path, error)
        if pass_invalid_values:
            update = True
        if strict_validation:
            raise jsonschema.ValidationError(errmsg)
        else:
            warnings.warn(errmsg, ValidationWarning)
    return update

def _check_value(value, schema, validator_context):
    """
    Perform the actual validation.
    """

    validator_resolver = validator_context.resolver

    temp_schema = {
        '$schema':
        'http://stsci.edu/schemas/asdf-schema/0.1.0/asdf-schema'}
    print('schema =', schema)
    temp_schema.update(schema)
    validator = asdfschema.get_validator(temp_schema,
                                          validator_context,
                                          validator_callbacks,
                                          validator_resolver)

    #value = yamlutil.custom_tree_to_tagged_tree(value, validator_context)
    validator.validate(value, _schema=temp_schema)
    validator_context.close()

def _validate(attr, instance, schema, ctx):
    tagged_tree = yamlutil.custom_tree_to_tagged_tree(instance, ctx)
    return _value_change(attr, tagged_tree, schema, False, strict_validation, ctx)

def _get_schema_for_property(schema, attr):
    subschema = schema.get('properties', {}).get(attr, None)
    print('XXXX _get_schema_for_property', schema)
    if subschema is not None:
        return subschema
    for combiner in ['allOf', 'anyOf']:
        for subschema in schema.get(combiner, []):
            subsubschema = _get_schema_for_property(subschema, attr)
            if subsubschema != {}:
                return subsubschema
    return {}


class DNode(UserDict):

    _tag = None
    _ctx = None

    def __init__(self, node=None, parent=None, name=None):

        if node is None:
            self.__dict__['_data']= {}
        elif isinstance(node, dict):
            self.__dict__['_data'] = node
        else:
            raise ValueError("Initializer only accepts dicts")
        self._x_schema = None
        self._schema_uri = None
        self._parent = parent
        self._name = name
        # else:
        #     self.data = node.data

    @property
    def ctx(self):
        if self._ctx is None:
            DNode._ctx = asdf.AsdfFile()
        return self._ctx
    
   
    def __getattr__(self, key):
        """
        Permit accessing dict keys as attributes, assuming they are legal Python
        variable names.
        """
        if key in self._data:
            print('---------- (getattr) key = ', key)
            value = self._data[key]
            if isinstance(value, dict):
                return DNode(value, parent=self, name=key)
            elif isinstance(value, list):
                return LNode(value)
            else:
                return value
        else:
            raise KeyError(f"No such key ({key}) found in node")

    def __setattr__(self, key, value):
        """
        Permit assigning dict keys as attributes.
        """
        if key[0] != '_':
            if key in self._data:
                print('***** (setattr)', key)
                if validate:
                    print('._data', self._data)
                    self._schema()
                    schema = self._x_schema.get('properties').get(key, None)
                    print('schema from __setattr__:', key, schema)
                    if _validate(key, value, schema, self.ctx):
                        self._data[key] = value
                self.__dict__['_data'][key] = value
            else:
                raise KeyError(f"No such key ({key}) found in node")
        else:
            self.__dict__[key] = value

    def _schema(self):
        """
        If not overridden by a subclass, it will search for a schema from 
        the parent class, recursing if necessary until one is found.
        """
        if self._x_schema is None:
            parent_schema = self._parent._schema()
            print('parent_schema', parent_schema)
            # Extract the subschema corresponding to this node.
            subschema = _get_schema_for_property(parent_schema, self._name)
            print(subschema)
            self._x_schema = subschema
    # def __getindex__(self, key):
    #     return self.data[key]

    # def __setindex__(self, key, value):
    #     self.data[key] = value

class LNode(UserList):

    _tag = None
    def __init__(self, node=None):
        if node is None:
            self.data = []
        elif isinstance(node, list):
            self.data = node
        else:
            raise ValueError("Initalizer only accepts lists")
        # else:
        #     self.data = node.data

    def __getitem__(self, index):
        value = self.data[index]
        if isinstance(value, dict):
            return DNode(value)
        elif isinstance(value, list):
            return LNode(value)
        else:
            return value

class TaggedObjectNode(DNode):
    """
    Expects subclass to define a class instance of _tag
    """

    @property
    def tag(self):
        return self._tag

    def _schema(self):
        if self._x_schema is None:
            self._x_schema = self.get_schema()
        return self._x_schema



    def get_schema(self):
        """Retrieve the schema associated with this tag"""
        extension_manager = self.ctx.extension_manager
        tag_def = extension_manager.get_tag_definition(self.tag)
        schema_uri = tag_def.schema_uri
        print(schema_uri)
        schema = asdfschema._load_schema_cached(
            schema_uri, self.ctx, False, False)
        print('zzzzzzzz', schema)
        return schema

class TaggedListNode(LNode):

    @property
    def tag(self):
        return self._tag


class TaggedObjectNodeConverter(Converter):
    """
    This class is intended to be subclassed for specific tags
    """

    # tags = [
    #     "tag:stsci.edu:datamodels/program-*"
    # ]
    # types = ["stdatamodels.stnode.Program"]

    tags = []
    types = []

    def to_yaml_tree(self, obj, tags, ctx): 
        return obj

    def from_yaml_tree(self, node, tag, ctx):
        return (node)

###################################
#
# Roman section
#
###################################

class WfiScienceRaw(TaggedObjectNode):
    _tag = "tag:stsci.edu:datamodels/roman/wfi_science_raw-1.0.0"

class WfiScienceRawConverter(TaggedObjectNodeConverter):
    tags = ["tag:stsci.edu:datamodels/roman/wfi_science_raw-*"]
    types = ["roman_datamodels.stnode.WfiScienceRaw"]

    def to_yaml_tree(self, obj, tags, ctx):
        return obj._data

    def from_yaml_tree(self, node, tag, ctx):
        return WfiScienceRaw(node)


class WfiImage(TaggedObjectNode):
    _tag = "tag:stsci.edu:datamodels/roman/wfi_image-1.0.0"

class WfiImageConverter(TaggedObjectNodeConverter):
    tags = ["tag:stsci.edu:datamodels/roman/wfi_image-*"]
    types = ["roman_datamodels.stnode.WfiImage"]

    def to_yaml_tree(self, obj, tags, ctx):
        return obj._data

    def from_yaml_tree(self, node, tag, ctx):
        return WfiImage(node)

class WfiMode(TaggedObjectNode):
    _tag = "tag:stsci.edu:datamodels/roman/wfi_mode-1.0.0"

class WfiModeConverter(TaggedObjectNodeConverter):
    tags = ["tag:stsci.edu:datamodels/roman/wfi_mode-*"]
    types = ["roman_datamodels.stnode.WfiMode"]

    def to_yaml_tree(self, obj, tags, ctx):
        return obj._data

    def from_yaml_tree(self, node, tag, ctx):
        return WfiMode(node)

class Exposure(TaggedObjectNode):
    _tag = "tag:stsci.edu:datamodels/roman/exposure-1.0.0"

class ExposureConverter(TaggedObjectNodeConverter):
    tags = ["tag:stsci.edu:datamodels/roman/exposure-*"]
    types = ["roman_datamodels.stnode.Exposure"]

    def to_yaml_tree(self, obj, tags, ctx):
        return obj._data

    def from_yaml_tree(self, node, tag, ctx):
        return Exposure(node)

class Wfi(TaggedObjectNode):
    _tag = "tag:stsci.edu:datamodels/roman/wfi-1.0.0"

class WfiConverter(TaggedObjectNodeConverter):
    tags = ["tag:stsci.edu:datamodels/roman/wfi-*"]
    types = ["roman_datamodels.stnode.Wfi"]

    def to_yaml_tree(self, obj, tags, ctx):
        return obj._data

    def from_yaml_tree(self, node, tag, ctx):
        return Wfi(node)

