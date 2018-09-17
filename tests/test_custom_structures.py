import unittest
import logging
import xml.etree.ElementTree as Et

import pytest

from opcua import ua, Server
import opcua.common.type_dictionary_buider
from opcua.common.type_dictionary_buider import OPCTypeDictionaryBuilder, DataTypeDictionaryBuilder
from opcua.common.type_dictionary_buider import get_ua_class, StructNode

port_num = 48540
ns_urn = 'http://test.freeopcua.github.io'


pytestmark = pytest.mark.asyncio


def to_camel_case(name):
    func = getattr(opcua.common.type_dictionary_buider, '_to_camel_case')
    return func(name)


def reference_generator(source_id, target_id, reference_type, is_forward=True):
    func = getattr(opcua.common.type_dictionary_buider, '_reference_generator')
    return func(source_id, target_id, reference_type, is_forward)


def set_up_test_tree():
    ext_head_attributes = {'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance', 'xmlns:tns': ns_urn,
                           'DefaultByteOrder': 'LittleEndian', 'xmlns:opc': 'http://opcfoundation.org/BinarySchema/',
                           'xmlns:ua': 'http://opcfoundation.org/UA/', 'TargetNamespace': ns_urn}

    test_etree = Et.ElementTree(Et.Element('opc:TypeDictionary', ext_head_attributes))
    name_space = Et.SubElement(test_etree.getroot(), 'opc:Import')
    name_space.attrib['Namespace'] = 'http://opcfoundation.org/UA/'
    return test_etree


@pytest.fixture(scope="module")
async def _srv(server):
    class Srv:
        pass
    srv = Srv()
    srv.srv = server
    srv.idx = await srv.srv.register_namespace(ns_urn)
    yield srv

    
@pytest.fixture
async def srv(_srv):
    _srv.test_etree = set_up_test_tree()
    _srv.opc_type_builder = OPCTypeDictionaryBuilder(ns_urn)
    _srv.dict_builder = DataTypeDictionaryBuilder(_srv.srv, _srv.idx, ns_urn, 'TestDict')
    await _srv.dict_builder.init()
    _srv.init_counter = getattr(_srv.dict_builder, '_id_counter')
    yield _srv
    curr_counter = getattr(_srv.dict_builder, '_id_counter')
    trash_nodes = []
    for counter in range(_srv.init_counter, curr_counter + 1):
        trash_nodes.append(_srv.srv.get_node('ns={0};i={1}'.format(_srv.idx, str(counter))))
    await _srv.srv.delete_nodes(trash_nodes)


async def test_camel_case_1():
    case = 'TurtleActionlibShapeActionFeedback'
    result = to_camel_case('turtle_actionlib/ShapeActionFeedback')
    assert result == case


async def test_camel_case_2():
    case = 'HelloWorldFffD'
    result = to_camel_case('Hello#world+fff_**?&&d')
    assert result == case


async def test_opc_type_dict_process_type_opc(srv):
    case = 'opc:Boolean'
    result = getattr(srv.opc_type_builder, '_process_type')('Boolean')
    assert result == case


async def test_opc_type_dict_process_type_tns(srv):
    case = 'tns:CustomizedStruct'
    result = getattr(srv.opc_type_builder, '_process_type')('CustomizedStruct')
    assert result == case


async def test_opc_type_dict_append_struct_1(srv):
    case = {'BaseType': 'ua:ExtensionObject',
            'Name': 'CustomizedStruct'}
    result = srv.opc_type_builder.append_struct('CustomizedStruct')
    assert result.attrib == case


async def test_opc_type_dict_append_struct_2(srv):
    case = {'BaseType': 'ua:ExtensionObject',
            'Name': 'CustomizedStruct'}
    result = srv.opc_type_builder.append_struct('customized_#?+`struct')
    assert result.attrib == case


async def test_opc_type_dict_add_field_1(srv):
    structure_name = 'CustomizedStruct'
    srv.opc_type_builder.append_struct(structure_name)
    srv.opc_type_builder.add_field(ua.VariantType.Boolean, 'id', structure_name)
    case = {'TypeName': 'opc:Boolean',
            'Name': 'id'}
    struct_dict = getattr(srv.opc_type_builder, '_structs_dict')
    result = list(struct_dict[structure_name])[0]
    assert result.attrib == case


async def test_opc_type_dict_add_field_2(srv):
    structure_name = 'CustomizedStruct'
    srv.opc_type_builder.append_struct(structure_name)
    srv.opc_type_builder.add_field('Boolean', 'id', structure_name)
    case = {'TypeName': 'opc:Boolean',
            'Name': 'id'}
    struct_dict = getattr(srv.opc_type_builder, '_structs_dict')
    result = list(struct_dict[structure_name])[0]
    assert result.attrib == case


async def test_opc_type_dict_add_field_3(srv):
    structure_name = 'CustomizedStruct'
    srv.opc_type_builder.append_struct(structure_name)
    srv.opc_type_builder.add_field(ua.VariantType.Boolean, 'id', structure_name, is_array=True)
    case = [{'TypeName': 'opc:Int32',
            'Name': 'NoOfid'},
            {'TypeName': 'opc:Boolean',
             'LengthField': 'NoOfid',
             'Name': 'id'}]
    struct_dict = getattr(srv.opc_type_builder, '_structs_dict')
    result = [item.attrib for item in list(struct_dict[structure_name])]
    assert result == case


async def test_opc_type_dict_get_dict_value(srv):
    structure_name = 'CustomizedStruct'
    srv.opc_type_builder.append_struct(structure_name)
    # external tree operation
    appended_struct = Et.SubElement(srv.test_etree.getroot(), 'opc:StructuredType')
    appended_struct.attrib['BaseType'] = 'ua:ExtensionObject'
    appended_struct.attrib['Name'] = to_camel_case(structure_name)

    srv.opc_type_builder.add_field(ua.VariantType.Boolean, 'id', structure_name)
    # external tree operation
    field = Et.SubElement(appended_struct, 'opc:Field')
    field.attrib['Name'] = 'id'
    field.attrib['TypeName'] = 'opc:Boolean'
    case = Et.tostring(srv.test_etree.getroot(), encoding='utf-8').decode("utf-8").replace(' ', '')
    result = srv.opc_type_builder.get_dict_value().decode("utf-8").replace(' ', '').replace('\n', '')
    assert result == case


async def test_reference_generator_1(srv):
    id1 = ua.NodeId(1, namespaceidx=2, nodeidtype=ua.NodeIdType.Numeric)
    id2 = ua.NodeId(2, namespaceidx=2, nodeidtype=ua.NodeIdType.Numeric)
    ref = ua.NodeId(ua.ObjectIds.HasEncoding, 0)
    result = reference_generator(id1, id2, ref)
    assert result.IsForward
    assert result.ReferenceTypeId == ref
    assert result.SourceNodeId == id1
    assert result.TargetNodeClass == ua.NodeClass.DataType
    assert result.TargetNodeId == id2


async def test_reference_generator_2(srv):
    id1 = ua.NodeId(1, namespaceidx=2, nodeidtype=ua.NodeIdType.Numeric)
    id2 = ua.NodeId(2, namespaceidx=2, nodeidtype=ua.NodeIdType.Numeric)
    ref = ua.NodeId(ua.ObjectIds.HasEncoding, 0)
    result = reference_generator(id1, id2, ref, False)
    assert not result.IsForward
    assert result.ReferenceTypeId == ref
    assert result.SourceNodeId == id1
    assert result.TargetNodeClass == ua.NodeClass.DataType
    assert result.TargetNodeId == id2


async def test_data_type_dict_general(srv):
    assert srv.dict_builder.dict_id is not None
    assert getattr(srv.dict_builder, '_type_dictionary') is not None


async def test_data_type_dict_nodeid_generator(srv):
    nodeid_generator = getattr(srv.dict_builder, '_nodeid_generator')
    result = nodeid_generator()
    assert isinstance(result, ua.NodeId)
    assert str(result.Identifier).isdigit()
    assert result.NamespaceIndex == srv.idx
    setattr(srv.dict_builder, '_id_counter', srv.init_counter)


async def test_data_type_dict_add_dictionary(srv):
    add_dictionary = getattr(srv.dict_builder, '_add_dictionary')
    dict_name = 'TestDict'
    dict_node = srv.srv.get_node(await add_dictionary(dict_name))
    assert await dict_node.get_browse_name() == ua.QualifiedName(dict_name, srv.idx)
    assert await dict_node.get_node_class() == ua.NodeClass.Variable
    assert (await dict_node.get_parent()).nodeid == ua.NodeId(ua.ObjectIds.OPCBinarySchema_TypeSystem, 0)
    assert ua.NodeId(ua.ObjectIds.HasComponent, 0) == (await dict_node.get_references(refs=ua.ObjectIds.HasComponent))[0].ReferenceTypeId
    assert await dict_node.get_type_definition() == ua.NodeId(ua.ObjectIds.DataTypeDictionaryType, 0)
    assert await dict_node.get_display_name() == ua.LocalizedText(dict_name)
    assert await dict_node.get_data_type() == ua.NodeId(ua.ObjectIds.ByteString)
    assert await dict_node.get_value_rank() == -1


async def test_data_type_dict_create_data_type(srv):
    type_name = 'CustomizedStruct'
    created_type = await srv.dict_builder.create_data_type(type_name)
    assert isinstance(created_type, StructNode)
    # Test data type node
    type_node = srv.srv.get_node(created_type.data_type)
    assert await type_node.get_browse_name() == ua.QualifiedName(type_name, srv.idx)
    assert await type_node.get_node_class() == ua.NodeClass.DataType
    assert (await type_node.get_parent()).nodeid == ua.NodeId(ua.ObjectIds.Structure, 0)
    assert ua.NodeId(ua.ObjectIds.HasSubtype, 0) == (await type_node.get_references(refs=ua.ObjectIds.HasSubtype))[0].ReferenceTypeId
    assert await type_node.get_display_name() == ua.LocalizedText(type_name)

    # Test description node
    desc_node = (await srv.srv.get_node(srv.dict_builder.dict_id).get_children())[0]
    assert await desc_node.get_browse_name() == ua.QualifiedName(type_name, srv.idx)
    assert await desc_node.get_node_class() == ua.NodeClass.Variable
    assert (await desc_node.get_parent()).nodeid == srv.dict_builder.dict_id
    assert ua.NodeId(ua.ObjectIds.HasComponent, 0) == (await desc_node.get_references(refs=ua.ObjectIds.HasComponent))[0].ReferenceTypeId
    assert await desc_node.get_type_definition() == ua.NodeId(ua.ObjectIds.DataTypeDescriptionType, 0)

    assert await desc_node.get_display_name() == ua.LocalizedText(type_name)
    assert await desc_node.get_data_type() == ua.NodeId(ua.ObjectIds.String)
    assert await desc_node.get_value() == type_name
    assert await desc_node.get_value_rank() == -1

    # Test object node
    obj_node = (await type_node.get_children(refs=ua.ObjectIds.HasEncoding))[0]
    assert await obj_node.get_browse_name() == ua.QualifiedName('Default Binary', 0)
    assert await obj_node.get_node_class() == ua.NodeClass.Object
    assert (await obj_node.get_references(refs=ua.ObjectIds.HasEncoding))[0].NodeId == type_node.nodeid
    assert ua.NodeId(ua.ObjectIds.HasEncoding, 0) == (await obj_node.get_references(refs=ua.ObjectIds.HasEncoding))[0].ReferenceTypeId
    assert await obj_node.get_type_definition() == ua.NodeId(ua.ObjectIds.DataTypeEncodingType, 0)
    assert await obj_node.get_display_name() == ua.LocalizedText('Default Binary')
    assert len(await obj_node.get_event_notifier()) == 0

    # Test links, three were tested above
    struct_node = srv.srv.get_node(ua.NodeId(ua.ObjectIds.Structure, 0))
    struct_children = await struct_node.get_children(refs=ua.ObjectIds.HasSubtype)
    assert type_node in struct_children
    dict_node = srv.srv.get_node(srv.dict_builder.dict_id)
    dict_children = await dict_node.get_children(refs=ua.ObjectIds.HasComponent)
    assert desc_node in dict_children
    assert obj_node in await type_node.get_children(ua.ObjectIds.HasEncoding)
    assert desc_node in await obj_node.get_children(refs=ua.ObjectIds.HasDescription)
    assert obj_node.nodeid == (await desc_node.get_references(refs=ua.ObjectIds.HasDescription, direction=ua.BrowseDirection.Inverse))[0].NodeId


async def test_data_type_dict_set_dict_byte_string(srv):
    structure_name = 'CustomizedStruct'
    await srv.dict_builder.create_data_type(structure_name)
    srv.dict_builder.add_field(ua.VariantType.Int32, 'id', structure_name)
    await srv.dict_builder.set_dict_byte_string()
    # external tree operation
    appended_struct = Et.SubElement(srv.test_etree.getroot(), 'opc:StructuredType')
    appended_struct.attrib['BaseType'] = 'ua:ExtensionObject'
    appended_struct.attrib['Name'] = to_camel_case(structure_name)

    # external tree operation
    field = Et.SubElement(appended_struct, 'opc:Field')
    field.attrib['Name'] = 'id'
    field.attrib['TypeName'] = 'opc:Int32'
    case = Et.tostring(srv.test_etree.getroot(), encoding='utf-8').decode("utf-8").replace(' ', '')
    result = (await srv.srv.get_node(srv.dict_builder.dict_id).get_value()).decode("utf-8").replace(' ', '').replace('\n', '')
    assert result == case


async def test_data_type_dict_add_field_1(srv):
    struct_name = 'CustomizedStruct'
    await srv.dict_builder.create_data_type(struct_name)
    srv.dict_builder.add_field(ua.VariantType.Int32, 'id', struct_name)
    await srv.dict_builder.set_dict_byte_string()
    await srv.srv.load_type_definitions()
    struct = get_ua_class(struct_name)
    assert struct.ua_types[0][0] == 'id'
    assert struct.ua_types[0][1] == 'Int32'
    struct_instance = struct()
    assert struct_instance.id == 0


async def test_data_type_dict_add_field_2(srv):
    struct_name = 'AnotherCustomizedStruct'
    await srv.dict_builder.create_data_type(struct_name)
    srv.dict_builder.add_field(ua.VariantType.Int32, 'id', struct_name, is_array=True)
    await srv.dict_builder.set_dict_byte_string()
    await srv.srv.load_type_definitions()
    struct = get_ua_class(struct_name)
    assert struct.ua_types[0][0] == 'id'
    assert struct.ua_types[0][1] == 'ListOfInt32'
    struct_instance = struct()
    assert isinstance(struct_instance.id, list)


async def test_struct_node_general(srv):
    struct_name = 'CustomizedStruct'
    struct_node = await srv.dict_builder.create_data_type(struct_name)
    assert getattr(struct_node, '_type_dict'), srv.dict_builder
    assert isinstance(struct_node.data_type, ua.NodeId)
    assert struct_node.name == struct_name


async def test_struct_node_add_field(srv):
    struct_name = 'CustomizedStruct'
    struct_node = await srv.dict_builder.create_data_type(struct_name)
    struct_node.add_field('id', ua.VariantType.Int32)
    await srv.dict_builder.set_dict_byte_string()
    await srv.srv.load_type_definitions()
    struct = get_ua_class(struct_name)
    assert struct.ua_types[0][0] == 'id'
    assert struct.ua_types[0][1] == 'Int32'
    struct_instance = struct()
    assert struct_instance.id == 0


async def test_get_ua_class_1(srv):
    struct_name = 'CustomizedStruct'
    struct_node = await srv.dict_builder.create_data_type(struct_name)
    struct_node.add_field('id', ua.VariantType.Int32)
    await srv.dict_builder.set_dict_byte_string()
    await srv.srv.load_type_definitions()
    try:
        assert get_ua_class(struct_name) is not None
    except AttributeError:
        pass


async def test_get_ua_class_2(srv):
    struct_name = '*c*u_stom-ized&Stru#ct'
    struct_node = await srv.dict_builder.create_data_type(struct_name)
    struct_node.add_field('id', ua.VariantType.Int32)
    await srv.dict_builder.set_dict_byte_string()
    await srv.srv.load_type_definitions()
    try:
        assert get_ua_class(struct_name) is not None
    except AttributeError:
        pass


async def test_functional_basic(srv):
    basic_struct_name = 'basic_structure'
    basic_struct = await srv.dict_builder.create_data_type(basic_struct_name)
    basic_struct.add_field('ID', ua.VariantType.Int32)
    basic_struct.add_field('Gender', ua.VariantType.Boolean)
    basic_struct.add_field('Comments', ua.VariantType.String)

    await srv.dict_builder.set_dict_byte_string()
    await srv.srv.load_type_definitions()

    basic_var = await srv.srv.nodes.objects.add_variable(ua.NodeId(namespaceidx=srv.idx), 'BasicStruct',
                                                    ua.Variant(None, ua.VariantType.Null),
                                                    datatype=basic_struct.data_type)

    basic_msg = get_ua_class(basic_struct_name)()
    basic_msg.ID = 3
    basic_msg.Gender = True
    basic_msg.Comments = 'Test string'
    await basic_var.set_value(basic_msg)

    basic_result = await basic_var.get_value()
    assert basic_result == basic_msg


async def test_functional_advance(srv):
    basic_struct_name = 'basic_structure'
    basic_struct = await srv.dict_builder.create_data_type(basic_struct_name)
    basic_struct.add_field('ID', ua.VariantType.Int32)
    basic_struct.add_field('Gender', ua.VariantType.Boolean)
    basic_struct.add_field('Comments', ua.VariantType.String)

    nested_struct_name = 'nested_structure'
    nested_struct = await srv.dict_builder.create_data_type(nested_struct_name)
    nested_struct.add_field('Name', ua.VariantType.String)
    nested_struct.add_field('Surname', ua.VariantType.String)
    nested_struct.add_field('Stuff', basic_struct)

    await srv.dict_builder.set_dict_byte_string()
    await srv.srv.load_type_definitions()

    basic_var = await srv.srv.nodes.objects.add_variable(ua.NodeId(namespaceidx=srv.idx), 'BasicStruct',
                                                    ua.Variant(None, ua.VariantType.Null),
                                                    datatype=basic_struct.data_type)

    basic_msg = get_ua_class(basic_struct_name)()
    basic_msg.ID = 3
    basic_msg.Gender = True
    basic_msg.Comments = 'Test string'
    await basic_var.set_value(basic_msg)

    nested_var = await srv.srv.nodes.objects.add_variable(ua.NodeId(namespaceidx=srv.idx), 'NestedStruct',
                                                     ua.Variant(None, ua.VariantType.Null),
                                                     datatype=nested_struct.data_type)

    nested_msg = get_ua_class(nested_struct_name)()
    nested_msg.Stuff = basic_msg
    nested_msg.Name = 'Max'
    nested_msg.Surname = 'Karl'
    await nested_var.set_value(nested_msg)

    basic_result = await basic_var.get_value()
    assert basic_result == basic_msg
    nested_result = await nested_var.get_value()
    assert nested_result == nested_msg