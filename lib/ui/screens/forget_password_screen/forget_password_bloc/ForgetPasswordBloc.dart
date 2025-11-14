import 'dart:async';
import 'package:validators/validators.dart';
import 'ForgetPasswordContract.dart';
import '../../../../domain/usecase/forget_password_use_case/ForgetPasswordUseCase.dart';

class ForgetPasswordBloc {
  final ForgotPasswordUseCase _useCase;

  final _stateController = StreamController<ForgetPasswordState>.broadcast();
  Stream<ForgetPasswordState> get state => _stateController.stream;
  ForgetPasswordState _currentState = ForgetPasswordState();

  final _eventController = StreamController<ForgetPasswordEvent>();
  Sink<ForgetPasswordEvent> get eventSink => _eventController.sink;

  ForgetPasswordBloc(this._useCase) {
    _eventController.stream.listen(_mapEventToState);
  }

  void _mapEventToState(ForgetPasswordEvent event) async {
    if (event is EmailChanged) {
      _currentState = _currentState.copyWith(
        email: event.email,
        emailError: isEmail(event.email) ? null : "Invalid email format",
      );
      _stateController.add(_currentState);

    } else if (event is SubmitForgetPassword) {
      // Validate email
      _currentState = _currentState.copyWith(
        emailError: isEmail(_currentState.email) ? null : "Invalid email format",
        generalError: null,
      );
      _stateController.add(_currentState);

      if (!_currentState.canSubmit) return;

      _currentState = _currentState.copyWith(isSubmitting: true);
      _stateController.add(_currentState);

      try {
        await _useCase.execute(_currentState.email);

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
