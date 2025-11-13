// lib/ui/screens/signup_screen/signup_bloc/signup_bloc.dart
import 'dart:async';
import '../../../../domain/usecase/signup_use_case/SignUpUseCase.dart';
import 'SignUpContract.dart';
import 'package:validators/validators.dart'; // For proper email validation

class SignupBloc {
  final SignUpUseCase _signUpUseCase;

  final _stateController = StreamController<SignupState>.broadcast();
  Stream<SignupState> get state => _stateController.stream;
  SignupState _currentState = SignupState();

  final _eventController = StreamController<SignupEvent>();
  Sink<SignupEvent> get eventSink => _eventController.sink;

  SignupBloc(this._signUpUseCase) {
    _eventController.stream.listen(_mapEventToState);
  }

  void _mapEventToState(SignupEvent event) async {
    if (event is NameChanged) {
      _currentState = _currentState.copyWith(
        name: event.name,
        nameError: event.name.isNotEmpty ? null : "Name cannot be empty",
      );
      _stateController.add(_currentState);

    } else if (event is EmailChanged) {
      _currentState = _currentState.copyWith(
        email: event.email,
        emailError: isEmail(event.email) ? null : "Invalid email format",
      );
      _stateController.add(_currentState);

    } else if (event is PasswordChanged) {
      _currentState = _currentState.copyWith(
        password: event.password,
        passwordError: event.password.length >= 6
            ? null
            : "Password too short",
      );
      _stateController.add(_currentState);

    } else if (event is ConfirmPasswordChanged) {
      _currentState = _currentState.copyWith(
        confirmPassword: event.confirmPassword,
        confirmPasswordError: event.confirmPassword == _currentState.password
            ? null
            : "Passwords do not match",
      );
      _stateController.add(_currentState);

    } else if (event is SignupSubmitted) {
      // Validate fields
      _currentState = _currentState.copyWith(
        nameError: _currentState.name.isNotEmpty ? null : "Name cannot be empty",
        emailError: isEmail(_currentState.email) ? null : "Invalid email format",
        passwordError: _currentState.password.length >= 6 ? null : "Password too short",
        confirmPasswordError: _currentState.password == _currentState.confirmPassword
            ? null
            : "Passwords do not match",
        generalError: null,
      );
      _stateController.add(_currentState);

      if (!_currentState.canSubmit) return;

      _currentState = _currentState.copyWith(isSubmitting: true);
      _stateController.add(_currentState);

      try {
        final user = await _signUpUseCase.execute(
          fullName: _currentState.name,
          email: _currentState.email,
          password: _currentState.password,
        );

        _currentState = _currentState.copyWith(
          isSubmitting: false,
          isSuccess: true,
          generalError: null,
        );
      } catch (e) {
        _currentState = _currentState.copyWith(
          isSubmitting: false,
          isSuccess: false,
          generalError: e.toString(),
        );
      }

      _stateController.add(_currentState);
    } else if (event is ClearGeneralError) {
      _currentState = _currentState.copyWith(generalError: null);
      _stateController.add(_currentState);
    }
  }

  void dispose() {
    _stateController.close();
    _eventController.close();
  }
}
