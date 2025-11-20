import '../../repository/AuthenticationRepository.dart';
import 'LogOutUseCase.dart';

class LogOutUseCaseImpl implements LogOutUseCase {
  final AuthenticationRepository _authRepo;

  LogOutUseCaseImpl(this._authRepo);

  @override
  Future<void> call() async {
    await _authRepo.logout();
  }
}