# CMakeLists.txt — builds the `libsubextract_paddle.so` JNI shim that wraps
# the Paddle Lite runtime. This file is only included in the Gradle build when
# the user has run `scripts/download_paddle_models.sh`, which drops Paddle Lite
# prebuilt libraries into `app/libs/paddle_lite/`.

cmake_minimum_required(VERSION 3.22.1)
project(subextract_paddle)

set(PADDLE_LITE_DIR "${CMAKE_SOURCE_DIR}/../../../libs/paddle_lite")

add_library(paddle_api_shared SHARED IMPORTED)
set_target_properties(paddle_api_shared PROPERTIES
    IMPORTED_LOCATION "${PADDLE_LITE_DIR}/${ANDROID_ABI}/libpaddle_api_shared.so")

add_library(subextract_paddle SHARED
    paddle_native.cpp
    ocr_pipeline.cpp
)

target_include_directories(subextract_paddle PRIVATE
    "${PADDLE_LITE_DIR}/${ANDROID_ABI}/include"
)

find_library(log-lib log)
find_library(android-lib android)
find_library(jnigraphics-lib jnigraphics)

target_link_libraries(subextract_paddle
    paddle_api_shared
    ${log-lib}
    ${android-lib}
    ${jnigraphics-lib}
)
