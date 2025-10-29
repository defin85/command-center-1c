1C:Enterprise 8 Remote Administration Utility Sample
----------------------------------------------------

This sample utility is intended for illustrating the usage 
of 1C:Enterprise 8 Administrative Service API for solving
1C:Enterprise 8 server cluster administration tasks.

The sample administration utility provides the following features:

 - getting the list of registered clusters
 - getting the list of infobases for the selected cluster
 - forced session termination for the selected cluster
 - managing the parameters of the selected infobase,
   which are related to blocking new sessions

The code used for the interaction with the administration server
of 1C:Enterprise 8 server cluster, which uses the 
1C:Enterprise 8 Administrative Service API, is located in 
the class sample.console.AgentAdminUtil.

Sample auxiliary classes are implemented for administrative
operations that require authentication:

 - sample.console.ui.operations.ClusterAuthenticatedOperation
   provides cluster authentication support
 
 - sample.console.ui.operations.InfoBaseAuthenticatedOperation
   provides infobase authentication support
   
The main class that is intended for running the utility
is sample.console.ui.AgentAdminConsole.   

Prerequisites for building and running the sample
--------------------------------------------------
You must have the following software installed on your computer:

  - Java SE Development Kit 5.0 or later

  - Apache Ant 1.6 or later

To build and run the sample using either Ant or Javac and Java, 
you need to set up the environment to ensure that the JDK and Ant 
directories are on the PATH.

Building
--------
To build the sample, complete the following steps:

1. In a command prompt/shell, go to the directory
   that contains this README.txt file.

2. Enter the following Ant command:

     ant compile

Running
-------
To run the sample, complete the following steps:

1. In a command prompt/shell, go to the directory
   that contains this README.txt file.

2. Enter the following Ant command:

     ant run
