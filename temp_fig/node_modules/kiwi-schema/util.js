"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
function quote(text) {
    return JSON.stringify(text);
}
exports.quote = quote;
function error(text, line, column) {
    var error = new Error(text);
    error.line = line;
    error.column = column;
    throw error;
}
exports.error = error;
