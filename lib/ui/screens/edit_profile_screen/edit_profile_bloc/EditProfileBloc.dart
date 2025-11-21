import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:constructEYE/domain/entities/UserEntity.dart';
import '../../../../domain/usecase/update_user_profile_use_case/UpdateUserProfileUseCase.dart';
import '../../../../domain/usecase/get_current_user_use_case/GetCurrentUserUseCase.dart';
import 'EditProfileContract.dart';

class EditProfileBloc {
  final ImagePicker _picker = ImagePicker();
  final UpdateUserProfileUseCase _updateUserProfileUseCase;
  final GetCurrentUserUseCase _getCurrentUserUseCase;

  EditProfileBloc(this._updateUserProfileUseCase, this._getCurrentUserUseCase) {
    _init();
  }

  // ---------------- STATE ----------------
  final _stateController = StreamController<EditProfileState>.broadcast();
  Stream<EditProfileState> get state => _stateController.stream;

  EditProfileState _currentState = EditProfileState(
    nameController: TextEditingController(),
    roleController: TextEditingController(),
    emailController: TextEditingController(),
    phoneController: TextEditingController(),
    companyController: TextEditingController(),
    isLoading: false,
  );

  EditProfileState get currentState => _currentState;

  // ---------------- EVENT ----------------
  final _eventController = StreamController<EditProfileEvent>();
  Sink<EditProfileEvent> get eventSink => _eventController.sink;

  void _init() async {
    _eventController.stream.listen(_mapEventToState);

    _emitLoading(true);
    try {
      final user = await _getCurrentUserUseCase.execute();
      if (user != null) {
        _currentState.nameController.text = user.fullName;
        _currentState.emailController.text = user.email;
        _currentState.roleController.text = user.role;
        _currentState.phoneController.text = user.phone;
        _currentState.companyController.text = user.company;

        _currentState = _currentState.copyWith(
          userEntity: user,
          imageUrl: user.profilePictureUrl, // <-- Firestore image
        );
      }
      _emitLoading(false);
    } catch (e) {
      _emitError(e.toString());
    }
  }


  void _mapEventToState(EditProfileEvent event) async {
    if (event is ChangeImageEvent) {
      final picked = await _picker.pickImage(source: ImageSource.gallery);
      if (picked != null) {
        _currentState = _currentState.copyWith(imagePath: picked.path);
        _stateController.add(_currentState);
      }
    } else if (event is SaveProfileEvent) {
      await _saveProfile();
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

  Future<void> _saveProfile() async {
    try {
      _emitLoading(true);

      File? imageFile;
      if (_currentState.imagePath != null) {
        imageFile = File(_currentState.imagePath!);
      }

      final user = UserEntity(
        uid: _currentState.userEntity!.uid,
        email: _currentState.emailController.text,
        fullName: _currentState.nameController.text,
        profilePictureUrl: _currentState.userEntity!.profilePictureUrl,
        phone: _currentState.phoneController.text,
        role: _currentState.roleController.text,
        company: _currentState.companyController.text,
      );

      final updatedUser = await _updateUserProfileUseCase.execute(
        user: user,
        newImage: imageFile,
      );

      _emitSuccess(updatedUser);
    } catch (e) {
      _emitError(e.toString());
    }
  }

  // ---------------- STATE HELPERS ----------------
  void _emitLoading(bool isLoading) {
    _currentState = _currentState.copyWith(isLoading: isLoading);
    _stateController.add(_currentState);
  }

  void _emitSuccess(UserEntity updatedUser) {
    _currentState = _currentState.copyWith(
      isLoading: false,
      isSuccess: true,
      userEntity: updatedUser,
    );
    _stateController.add(_currentState);
  }

  void _emitError(String msg) {
    _currentState = _currentState.copyWith(
      isLoading: false,
      errorMessage: msg,
    );
    _stateController.add(_currentState);
  }

  void dispose() {
    _stateController.close();
    _eventController.close();
  }
}
