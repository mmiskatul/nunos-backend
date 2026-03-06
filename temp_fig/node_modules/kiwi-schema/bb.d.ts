export declare class ByteBuffer {
    private _data;
    private _index;
    length: number;
    constructor(data?: Uint8Array);
    toUint8Array(): Uint8Array;
    readByte(): number;
    readByteArray(): Uint8Array;
    readVarFloat(): number;
    readVarUint(): number;
    readVarInt(): number;
    readString(): string;
    private _growBy;
    writeByte(value: number): void;
    writeByteArray(value: Uint8Array): void;
    writeVarFloat(value: number): void;
    writeVarUint(value: number): void;
    writeVarInt(value: number): void;
    writeString(value: string): void;
}
