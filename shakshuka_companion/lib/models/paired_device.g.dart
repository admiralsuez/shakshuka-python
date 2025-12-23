// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'paired_device.dart';

// **************************************************************************
// TypeAdapterGenerator
// **************************************************************************

class PairedDeviceAdapter extends TypeAdapter<PairedDevice> {
  @override
  final int typeId = 1;

  @override
  PairedDevice read(BinaryReader reader) {
    final numOfFields = reader.readByte();
    final fields = <int, dynamic>{
      for (int i = 0; i < numOfFields; i++) reader.readByte(): reader.read(),
    };
    return PairedDevice(
      serverUrl: fields[0] as String,
      token: fields[1] as String,
      deviceName: fields[2] as String,
      pairedAt: fields[3] as DateTime?,
    );
  }

  @override
  void write(BinaryWriter writer, PairedDevice obj) {
    writer
      ..writeByte(4)
      ..writeByte(0)
      ..write(obj.serverUrl)
      ..writeByte(1)
      ..write(obj.token)
      ..writeByte(2)
      ..write(obj.deviceName)
      ..writeByte(3)
      ..write(obj.pairedAt);
  }

  @override
  int get hashCode => typeId.hashCode;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is PairedDeviceAdapter &&
          runtimeType == other.runtimeType &&
          typeId == other.typeId;
}
