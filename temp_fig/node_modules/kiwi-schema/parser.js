"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const util_1 = require("./util");
exports.nativeTypes = [
    'bool',
    'byte',
    'float',
    'int',
    'string',
    'uint',
];
// These are special names on the object returned by compileSchema()
exports.reservedNames = [
    'ByteBuffer',
    'package',
];
let regex = /((?:-|\b)\d+\b|[=;{}]|\[\]|\[deprecated\]|\b[A-Za-z_][A-Za-z0-9_]*\b|\/\/.*|\s+)/g;
let identifier = /^[A-Za-z_][A-Za-z0-9_]*$/;
let whitespace = /^\/\/.*|\s+$/;
let equals = /^=$/;
let endOfFile = /^$/;
let semicolon = /^;$/;
let integer = /^-?\d+$/;
let leftBrace = /^\{$/;
let rightBrace = /^\}$/;
let arrayToken = /^\[\]$/;
let enumKeyword = /^enum$/;
let structKeyword = /^struct$/;
let messageKeyword = /^message$/;
let packageKeyword = /^package$/;
let deprecatedToken = /^\[deprecated\]$/;
function tokenize(text) {
    let parts = text.split(regex);
    let tokens = [];
    let column = 0;
    let line = 0;
    for (let i = 0; i < parts.length; i++) {
        let part = parts[i];
        // Keep non-whitespace tokens
        if (i & 1) {
            if (!whitespace.test(part)) {
                tokens.push({
                    text: part,
                    line: line + 1,
                    column: column + 1,
                });
            }
        }
        // Detect syntax errors
        else if (part !== '') {
            util_1.error('Syntax error ' + util_1.quote(part), line + 1, column + 1);
        }
        // Keep track of the line and column counts
        let lines = part.split('\n');
        if (lines.length > 1)
            column = 0;
        line += lines.length - 1;
        column += lines[lines.length - 1].length;
    }
    // End-of-file token
    tokens.push({
        text: '',
        line: line,
        column: column,
    });
    return tokens;
}
function parse(tokens) {
    function current() {
        return tokens[index];
    }
    function eat(test) {
        if (test.test(current().text)) {
            index++;
            return true;
        }
        return false;
    }
    function expect(test, expected) {
        if (!eat(test)) {
            let token = current();
            util_1.error('Expected ' + expected + ' but found ' + util_1.quote(token.text), token.line, token.column);
        }
    }
    function unexpectedToken() {
        let token = current();
        util_1.error('Unexpected token ' + util_1.quote(token.text), token.line, token.column);
    }
    let definitions = [];
    let packageText = null;
    let index = 0;
    if (eat(packageKeyword)) {
        packageText = current().text;
        expect(identifier, 'identifier');
        expect(semicolon, '";"');
    }
    while (index < tokens.length && !eat(endOfFile)) {
        let fields = [];
        let kind;
        if (eat(enumKeyword))
            kind = 'ENUM';
        else if (eat(structKeyword))
            kind = 'STRUCT';
        else if (eat(messageKeyword))
            kind = 'MESSAGE';
        else
            unexpectedToken();
        // All definitions start off the same
        let name = current();
        expect(identifier, 'identifier');
        expect(leftBrace, '"{"');
        // Parse fields
        while (!eat(rightBrace)) {
            let type = null;
            let isArray = false;
            let isDeprecated = false;
            // Enums don't have types
            if (kind !== 'ENUM') {
                type = current().text;
                expect(identifier, 'identifier');
                isArray = eat(arrayToken);
            }
            let field = current();
            expect(identifier, 'identifier');
            // Structs don't have explicit values
            let value = null;
            if (kind !== 'STRUCT') {
                expect(equals, '"="');
                value = current();
                expect(integer, 'integer');
                if ((+value.text | 0) + '' !== value.text) {
                    util_1.error('Invalid integer ' + util_1.quote(value.text), value.line, value.column);
                }
            }
            let deprecated = current();
            if (eat(deprecatedToken)) {
                if (kind !== 'MESSAGE') {
                    util_1.error('Cannot deprecate this field', deprecated.line, deprecated.column);
                }
                isDeprecated = true;
            }
            expect(semicolon, '";"');
            fields.push({
                name: field.text,
                line: field.line,
                column: field.column,
                type: type,
                isArray: isArray,
                isDeprecated: isDeprecated,
                value: value !== null ? +value.text | 0 : fields.length + 1,
            });
        }
        definitions.push({
            name: name.text,
            line: name.line,
            column: name.column,
            kind: kind,
            fields: fields,
        });
    }
    return {
        package: packageText,
        definitions: definitions,
    };
}
function verify(root) {
    let definedTypes = exports.nativeTypes.slice();
    let definitions = {};
    // Define definitions
    for (let i = 0; i < root.definitions.length; i++) {
        let definition = root.definitions[i];
        if (definedTypes.indexOf(definition.name) !== -1) {
            util_1.error('The type ' + util_1.quote(definition.name) + ' is defined twice', definition.line, definition.column);
        }
        if (exports.reservedNames.indexOf(definition.name) !== -1) {
            util_1.error('The type name ' + util_1.quote(definition.name) + ' is reserved', definition.line, definition.column);
        }
        definedTypes.push(definition.name);
        definitions[definition.name] = definition;
    }
    // Check fields
    for (let i = 0; i < root.definitions.length; i++) {
        let definition = root.definitions[i];
        let fields = definition.fields;
        if (definition.kind === 'ENUM' || fields.length === 0) {
            continue;
        }
        // Check types
        for (let j = 0; j < fields.length; j++) {
            let field = fields[j];
            if (definedTypes.indexOf(field.type) === -1) {
                util_1.error('The type ' + util_1.quote(field.type) + ' is not defined for field ' + util_1.quote(field.name), field.line, field.column);
            }
        }
        // Check values
        let values = [];
        for (let j = 0; j < fields.length; j++) {
            let field = fields[j];
            if (values.indexOf(field.value) !== -1) {
                util_1.error('The id for field ' + util_1.quote(field.name) + ' is used twice', field.line, field.column);
            }
            if (field.value <= 0) {
                util_1.error('The id for field ' + util_1.quote(field.name) + ' must be positive', field.line, field.column);
            }
            if (field.value > fields.length) {
                util_1.error('The id for field ' + util_1.quote(field.name) + ' cannot be larger than ' + fields.length, field.line, field.column);
            }
            values.push(field.value);
        }
    }
    // Check that structs don't contain themselves
    let state = {};
    let check = (name) => {
        let definition = definitions[name];
        if (definition && definition.kind === 'STRUCT') {
            if (state[name] === 1) {
                util_1.error('Recursive nesting of ' + util_1.quote(name) + ' is not allowed', definition.line, definition.column);
            }
            if (state[name] !== 2 && definition) {
                state[name] = 1;
                let fields = definition.fields;
                for (let i = 0; i < fields.length; i++) {
                    let field = fields[i];
                    if (!field.isArray) {
                        check(field.type);
                    }
                }
                state[name] = 2;
            }
        }
        return true;
    };
    for (let i = 0; i < root.definitions.length; i++) {
        check(root.definitions[i].name);
    }
}
function parseSchema(text) {
    let schema = parse(tokenize(text));
    verify(schema);
    return schema;
}
exports.parseSchema = parseSchema;
