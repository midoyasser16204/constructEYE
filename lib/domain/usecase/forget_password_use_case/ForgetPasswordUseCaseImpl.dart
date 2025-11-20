
import 'package:constructEYE/domain/repository/AuthenticationRepository.dart';

import 'ForgetPasswordUseCase.dart';

class ForgetPasswordUseCaseImpl implements ForgetPasswordUseCase {
  final AuthenticationRepository _repository;

  ForgetPasswordUseCaseImpl(this._repository);

  @override
  Future<void> execute(String email) {
    return _repository.forgotPassword(email: email);
  }
}
