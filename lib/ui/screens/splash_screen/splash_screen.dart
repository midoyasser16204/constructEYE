import 'package:flutter/material.dart';
import 'package:loading_animation_widget/loading_animation_widget.dart';
import '../../../core/colors/AppColors.dart';
import '../../../core/constants/AppConstants.dart';
import 'splash_bloc/splash_bloc.dart';
import 'splash_bloc/splash_contract.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  late final SplashBloc _bloc;

  @override
  void initState() {
    super.initState();
    _bloc = SplashBloc();
    _bloc.eventSink.add(SplashStarted());
  }

  @override
  void dispose() {
    _bloc.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final screenHeight = MediaQuery.of(context).size.height;
    final screenWidth = MediaQuery.of(context).size.width;

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      body: StreamBuilder<SplashState>(
        stream: _bloc.state,
        initialData: SplashState(),
        builder: (context, snapshot) {
          final state = snapshot.data!;

          // Navigate when finished
          if (state.isFinished) {
            Future.microtask(() {
              Navigator.pushReplacementNamed(context,AppConstants.loginScreenRoute);
            });
          }

          return Column(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              SizedBox(height: screenHeight * 0.05),

              Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Image.asset(
                      AppConstants.logoImage,
                      width: screenHeight * 0.6,
                      height: screenWidth * 0.6,
                    ),
                    SizedBox(height: screenHeight * 0.03),
                    Text(
                      AppConstants.appTagLine,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontSize: 16,
                        color: theme.textTheme.bodyMedium?.color, // automatically adapts to theme
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),

              Padding(
                padding: EdgeInsets.only(bottom: screenHeight * 0.06),
                child: state.isLoading
                    ? LoadingAnimationWidget.waveDots(
                        color: AppColors.secondaryColor,
                        size: screenHeight * 0.045,
                      )
                    : const SizedBox.shrink(),
              ),
            ],
          );
        },
      ),
    );
  }
}
