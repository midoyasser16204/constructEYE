import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../../../../core/constants/AppConstants.dart';
import 'EditProfileContract.dart';

class EditProfileBloc {
  final ImagePicker _picker = ImagePicker();

  // ---------------- STATE ----------------
  final _stateController = StreamController<EditProfileState>.broadcast();
  Stream<EditProfileState> get state => _stateController.stream;

  EditProfileState _currentState = EditProfileState(
    nameController: TextEditingController(text: AppConstants.editProfileNameAll),
    roleController: TextEditingController(text: AppConstants.defaultRole),
    emailController: TextEditingController(text: AppConstants.defaultEmail),
    phoneController: TextEditingController(text: AppConstants.defaultPhone),
    companyController: TextEditingController(text: AppConstants.companyName),
  );

  EditProfileState get currentState => _currentState;

  // ---------------- EVENT ----------------
  final _eventController = StreamController<EditProfileEvent>();
  Sink<EditProfileEvent> get eventSink => _eventController.sink;

  EditProfileBloc() {
    _eventController.stream.listen(_mapEventToState);
  }

  void _mapEventToState(EditProfileEvent event) async {
    if (event is ChangeImageEvent) {
      final picked = await _picker.pickImage(source: ImageSource.gallery);
      if (picked != null) {
        _currentState = _currentState.copyWith(imagePath: picked.path);
        _stateController.add(_currentState);
      }
    } else if (event is SaveProfileEvent) {
      debugPrint("PROFILE SAVED!");
      // هنا ممكن تضيف منطق الحفظ للسيرفر أو Local Storage
    } else if (event is NameChanged) {
      _currentState.nameController.text = event.name;
      _stateController.add(_currentState);
    } else if (event is RoleChanged) {
      _currentState.roleController.text = event.role;
      _stateController.add(_currentState);
    } else if (event is EmailChanged) {
      _currentState.emailController.text = event.email;
      _stateController.add(_currentState);
    } else if (event is PhoneChanged) {
      _currentState.phoneController.text = event.phone;
      _stateController.add(_currentState);
    } else if (event is CompanyChanged) {
      _currentState.companyController.text = event.company;
      _stateController.add(_currentState);
    }
  }

  void dispose() {
    _stateController.close();
    _eventController.close();
  }
}
