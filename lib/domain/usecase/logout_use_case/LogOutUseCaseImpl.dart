import '../../repository/AuthenticationRepository.dart';
import 'LogOutUseCase.dart';

class LogoutUseCaseImpl implements LogoutUseCase {
  final AuthenticationRepository _authRepo;

  LogoutUseCaseImpl(this._authRepo);

  @override
  Future<void> call() async {
    await _authRepo.logout();
  }
}