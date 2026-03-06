"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const bb_1 = require("./bb");
let types = ['bool', 'byte', 'int', 'uint', 'float', 'string'];
let kinds = ['ENUM', 'STRUCT', 'MESSAGE'];
function decodeBinarySchema(buffer) {
    let bb = buffer instanceof bb_1.ByteBuffer ? buffer : new bb_1.ByteBuffer(buffer);
    let definitionCount = bb.readVarUint();
    let definitions = [];
    // Read in the schema
    for (let i = 0; i < definitionCount; i++) {
        let definitionName = bb.readString();
        let kind = bb.readByte();
        let fieldCount = bb.readVarUint();
        let fields = [];
        for (let j = 0; j < fieldCount; j++) {
            let fieldName = bb.readString();
            let type = bb.readVarInt();
            let isArray = !!(bb.readByte() & 1);
            let value = bb.readVarUint();
            fields.push({
                name: fieldName,
                line: 0,
                column: 0,
                type: kinds[kind] === 'ENUM' ? null : type,
                isArray: isArray,
                isDeprecated: false,
                value: value,
            });
        }
        definitions.push({
            name: definitionName,
            line: 0,
            column: 0,
            kind: kinds[kind],
            fields: fields,
        });
    }
    // Bind type names afterwards
    for (let i = 0; i < definitionCount; i++) {
        let fields = definitions[i].fields;
        for (let j = 0; j < fields.length; j++) {
            let field = fields[j];
            let type = field.type;
            if (type !== null && type < 0) {
                if (~type >= types.length) {
                    throw new Error('Invalid type ' + type);
                }
                field.type = types[~type];
            }
            else {
                if (type !== null && type >= definitions.length) {
                    throw new Error('Invalid type ' + type);
                }
                field.type = type === null ? null : definitions[type].name;
            }
        }
    }
    return {
        package: null,
        definitions: definitions,
    };
}
exports.decodeBinarySchema = decodeBinarySchema;
function encodeBinarySchema(schema) {
    let bb = new bb_1.ByteBuffer();
    let definitions = schema.definitions;
    let definitionIndex = {};
    bb.writeVarUint(definitions.length);
    for (let i = 0; i < definitions.length; i++) {
        definitionIndex[definitions[i].name] = i;
    }
    for (let i = 0; i < definitions.length; i++) {
        let definition = definitions[i];
        bb.writeString(definition.name);
        bb.writeByte(kinds.indexOf(definition.kind));
        bb.writeVarUint(definition.fields.length);
        for (let j = 0; j < definition.fields.length; j++) {
            let field = definition.fields[j];
            let type = types.indexOf(field.type);
            bb.writeString(field.name);
            bb.writeVarInt(type === -1 ? definitionIndex[field.type] : ~type);
            bb.writeByte(field.isArray ? 1 : 0);
            bb.writeVarUint(field.value);
        }
    }
    return bb.toUint8Array();
}
exports.encodeBinarySchema = encodeBinarySchema;
