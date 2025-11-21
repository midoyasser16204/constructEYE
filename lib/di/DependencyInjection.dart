import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:constructEYE/data/repository/UserRepositoryImpl.dart';
import 'package:constructEYE/domain/repository/UserRepository.dart';
import 'package:constructEYE/domain/usecase/get_current_user_use_case/GetCurrentUserUseCase.dart';
import 'package:constructEYE/domain/usecase/get_current_user_use_case/GetCurrentUserUseCaseImpl.dart';
import 'package:constructEYE/domain/usecase/update_user_profile_use_case/UpdateUserProfileUseCase.dart';
import 'package:constructEYE/domain/usecase/update_user_profile_use_case/UpdateUserProfileUseCaseImpl.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:get_it/get_it.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../data/data_source/shared_pref/SharedPrefDataSource.dart';
import '../data/data_source/shared_pref/SharedPrefDataSourceImpl.dart';
import '../data/repository/AuthenticationRepositoryImpl.dart';
import '../domain/repository/AuthenticationRepository.dart';
import '../domain/usecase/forget_password_use_case/ForgetPasswordUseCase.dart';
import '../domain/usecase/forget_password_use_case/ForgetPasswordUseCaseImpl.dart';
import '../domain/usecase/login_use_case/LoginUseCase.dart';
import '../domain/usecase/login_use_case/LoginUseCaseImpl.dart';
import '../domain/usecase/logout_use_case/LogOutUseCase.dart';
import '../domain/usecase/logout_use_case/LogOutUseCaseImpl.dart';
import '../domain/usecase/signup_use_case/SignUpUseCase.dart';
import '../domain/usecase/signup_use_case/SignUpUseCaseImpl.dart';
import '../ui/screens/edit_profile_screen/edit_profile_bloc/EditProfileBloc.dart';
import '../ui/screens/forget_password_screen/forget_password_bloc/ForgetPasswordBloc.dart';
import '../ui/screens/login_screen/login_bloc/LogInBloc.dart';
import '../ui/screens/profile_screen/profile_bloc/ProfileBloc.dart';
import '../ui/screens/signup_screen/signup_bloc/SignUpBloc.dart';
import '../ui/screens/splash_screen/splash_bloc/SplashBloc.dart';

final getIt = GetIt.instance;

/// Initialize all dependencies
Future<void> configureDependencies() async {
  // ========== External Dependencies ==========
  // Register SharedPreferences as a singleton (async initialization)
  final sharedPreferences = await SharedPreferences.getInstance();
  getIt.registerSingleton<SharedPreferences>(sharedPreferences);

  // Register Firebase instances as singletons
  getIt.registerLazySingleton<FirebaseAuth>(() => FirebaseAuth.instance);
  getIt.registerLazySingleton<FirebaseFirestore>(
    () => FirebaseFirestore.instance,
  );
  getIt.registerLazySingleton<FirebaseStorage>(() => FirebaseStorage.instance);

  // ========== Data Sources ==========
  getIt.registerLazySingleton<SharedPrefDataSource>(
    () => SharedPrefDataSourceImpl(getIt<SharedPreferences>()),
  );

  // ========== Repositories ==========
  getIt.registerLazySingleton<AuthenticationRepository>(
    () => AuthenticationRepositoryImpl(
      firebaseAuth: getIt<FirebaseAuth>(),
      firestore: getIt<FirebaseFirestore>(),
      sharedPref: getIt<SharedPrefDataSource>(),
    ),
  );

  getIt.registerLazySingleton<UserRepository>(
    () => UserRepositoryImpl(
      firestore: getIt<FirebaseFirestore>(),
      sharedPref: getIt<SharedPrefDataSource>(),
      storage: getIt<FirebaseStorage>(),
    ),
  );

  // ========== Use Cases ==========
  getIt.registerLazySingleton<LoginUseCase>(
    () => LoginUseCaseImpl(getIt<AuthenticationRepository>()),
  );

  getIt.registerLazySingleton<SignUpUseCase>(
    () => SignUpUseCaseImpl(getIt<AuthenticationRepository>()),
  );

  getIt.registerLazySingleton<LogOutUseCase>(
    () => LogOutUseCaseImpl(getIt<AuthenticationRepository>()),
  );

  getIt.registerLazySingleton<ForgetPasswordUseCase>(
    () => ForgetPasswordUseCaseImpl(getIt<AuthenticationRepository>()),
  );

  getIt.registerLazySingleton<GetCurrentUserUseCase>(
    () => GetCurrentUserUseCaseImpl(getIt<UserRepository>()),
  );

  getIt.registerLazySingleton<UpdateUserProfileUseCase>(
    () => UpdateUserProfileUseCaseImpl(getIt<UserRepository>()),
  );
  // ========== BLoCs ==========
  // BLoCs are registered as factories so each screen gets a new instance
  getIt.registerFactory<LoginBloc>(() => LoginBloc(getIt<LoginUseCase>()));

  getIt.registerFactory<SignupBloc>(() => SignupBloc(getIt<SignUpUseCase>()));

  getIt.registerFactory<ForgetPasswordBloc>(
    () => ForgetPasswordBloc(getIt<ForgetPasswordUseCase>()),
  );

  getIt.registerFactory<SplashBloc>(
    () => SplashBloc(getIt<SharedPrefDataSource>()),
  );

  getIt.registerFactory<ProfileBloc>(
    () => ProfileBloc(getIt<GetCurrentUserUseCase>(), getIt<LogOutUseCase>()),
  );

  getIt.registerFactory<EditProfileBloc>(
    () => EditProfileBloc(getIt<UpdateUserProfileUseCase>(), getIt<GetCurrentUserUseCase>()),
  );
}
