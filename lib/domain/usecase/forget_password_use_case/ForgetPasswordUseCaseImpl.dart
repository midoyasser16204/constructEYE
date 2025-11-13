
import 'package:constructEYE/domain/repository/AuthenticationRepository.dart';

import 'ForgetPasswordUseCase.dart';

class ForgotPasswordUseCaseImpl implements ForgotPasswordUseCase {
  final AuthenticationRepository _repository;

  ForgotPasswordUseCaseImpl(this._repository);

  @override
  Future<void> execute(String email) {
    return _repository.forgotPassword(email: email);
  }
}
