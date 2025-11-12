import 'package:constructEYE/core/colors/AppColors.dart';
import 'package:constructEYE/core/constants/AppConstants.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:loading_animation_widget/loading_animation_widget.dart';
import 'splash_bloc/splash_bloc.dart';
import 'splash_bloc/splash_contract.dart';

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final screenHeight = MediaQuery.of(context).size.height;
    final screenWidth = MediaQuery.of(context).size.width;

    return BlocProvider(
      create: (_) => SplashBloc()..add(SplashStarted()),
      child: BlocListener<SplashBloc, SplashUiState>(
        listener: (context, state) {
          if (state is SplashFinished) {
            Navigator.pushReplacementNamed(context, '/login');
          }
        },
        child: Scaffold(
          backgroundColor: AppColors.background,
          body: Column(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              SizedBox(height: screenHeight * 0.05),

              Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Image.asset(
                      AppConstants.logoImage,
                      width: screenHeight * 0.3,
                      height: screenWidth * 0.3,
                    ),
                    SizedBox(height: screenHeight * 0.03),
                    const Text(
                      AppConstants.appTagLine,
                      style: TextStyle(
                        fontSize: 16,
                        color: AppColors.text,
                      ),
                    ),
                  ],
                ),
              ),

              Padding(
                padding: EdgeInsets.only(bottom: screenHeight * 0.06),
                child: LoadingAnimationWidget.waveDots(
                  color: AppColors.secondaryColor,
                  size: screenHeight * 0.045,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
