import 'package:constructEYE/core/constants/AppConstants.dart';
import 'package:constructEYE/ui/components/TextInputField.dart';
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'projects_bloc/projectsbloc.dart';
import 'projects_bloc/projectscontract.dart';
import 'package:constructEYE/ui/components/project_card.dart';

class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({super.key});

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen> {
  final ProjectsBloc _bloc = ProjectsBloc();
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _bloc.eventSink.add(LoadProjects());
  }

  @override
  void dispose() {
    _bloc.dispose();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final screenHeight = MediaQuery.of(context).size.height;

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      body: Stack(
        children: [
          StreamBuilder<ProjectsState>(
            stream: _bloc.state,
            initialData: ProjectsState(),
            builder: (context, snapshot) {
              final state = snapshot.data!;

              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Top Header
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.only(
                      top: 70,
                      left: 20,
                      right: 20,
                      bottom: 25,
                    ),
                    decoration: BoxDecoration(
                      color: theme.primaryColor,
                      borderRadius: const BorderRadius.only(
                        bottomLeft: Radius.circular(26),
                        bottomRight: Radius.circular(26),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          "Select Your Project",
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 20),

                        // Search Box
                        TextInputField(
                          title: "",
                          hintText: "Search Project",
                          controller: _searchController,
                          svgPrefixIcon: AppConstants.searchIcon,
                          onChanged: (value) {
                            _bloc.eventSink.add(SearchQueryChanged(value));
                          },
                        ),
                      ],
                    ),
                  ),

                  SizedBox(height: screenHeight * 0.02),

                  // Projects List
                  Expanded(
                    child: state.isLoading
                        ? Center(
                            child: CircularProgressIndicator(
                              color: theme.primaryColor,
                            ),
                          )
                        : ListView.builder(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 5,
                            ),
                            itemCount: state.filteredProjects.length,
                            itemBuilder: (context, index) {
                              final project = state.filteredProjects[index];
                              return ProjectCard(
                                imagePath: AppConstants.logoImage,
                                location: "asdsa",
                                progress: 20,
                                status: "active",
                                title: "qweqwe",
                              );
                            },
                          ),
                  ),
                ],
              );
            },
          ),

          // Custom Floating Button
          Positioned(
            bottom: 20,
            right: 20,
            child: GestureDetector(
              onTap: () {
                // أضف هنا الأكشن اللي عايزه
              },
              child:  SvgPicture.asset(
                  AppConstants.addProjectIcon,
                  width: screenHeight * 0.1, // حجم الأيقونة
                  height: screenHeight * 0.1,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
