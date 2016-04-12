#Wind Turbine Locator – ArcPy Geoprocessing tool

This repository contains a Python file for locating sites for wind turbines in a study area (e.g. polygon). This tool relies on the Esri ArcPy library and requires a license of ArcGIS Desktop and the Spatial Analyst extension. The tool requires a polygon layer to define the boundary for determining the location of wind turbines. It also requires a digital elevation data model (DEM) and a slope raster.     

Please keep in mind this is a simplistic model for suggesting locations for wind turbines.  This tool was developed for a conference paper competition in 2011 and is meant to be an example of one approach to locate wind turbines.

You can find a more detailed description of the methodology behind the tool at this blog post.

The data used for this model can be downloaded from Amazon S3: [Sample File Geodatabase] (https://s3-us-west-2.amazonaws.com/githubik/WF_Turbine_Sample.gdb.zip)

##How it works

The first step in the model is to select cells, within the polygon feature, that have a slope less than 10%.  These cells are then converted to points and run through a candidate selection phase.  There are three criteria that a point must meet to qualify as a valid turbine location.  The first criterion is met if the difference between the bottom of the turbine blade and the minimum distance, contained in the 4.06 sq. mile buffer, is three times greater than the difference in elevation within the same buffered area.  The second criterion is met if the slope, along the upstream line, does not exceed 2%.  The third criterion is similar to the second, but analyzes the slope downstream.  Upstream and downstream paths were determined from the 2010 average wind direction for that location.  If all of these criteria are met, then the point is marked as a potential turbine location.  The model then generates a buffer around the turbine that is five turbine diameters in length.  Another buffer is generated along the upstream and downstream lines, which is three diameters in width.  If any point falls within either of these buffers, it is disqualified from the candidate list.  The model will continue to run until all turbine locations are identified. 

![Turbine Locator Model]( /Images/turbinelocatormodel.PNG)

##How to Install
1. Copy the WindTurbineLocator.py to a folder on a computer that has access to an ArcGIS Desktop license. 
2. Download the sample file geodatabase or create a new one with the required data sets.
3. Set the following parameters in the WindTurbineLocator.py file
	* dataWorkspace - The location of the output file geodatabase
	* demInputLayer - The path to the DEM raster
	* slopeInputLayer - The path to the Slope raster
	* windFarmBoundaryLayer - The path to the polygon layer that will be used as the wind farm boundary
	* minTotalMW - Minimum total megawatts the site should generate

##How to Execute
At a command prompt, execute WindTurbinLocator.py.  There are currently no command parameters, but the tool can be easily modified to accept parameters or connected to an ArcGIS toolbox.

Below is an example of the output for 11 turbines.  Because the tool orders the search by elevation, the higher elevations will be used first for potential sites.

![Turbine tool sample output]( /Images/turbine_sampleoutput.png)

##Known Limitations
1. Performance - The tool can take a while to run if the study area is large and/or the resolution of the DEM and slope rasters are also high (e.g. 10 m).  
2. Requires ArcGIS Desktop and the Spatial Analysis extension

##Future Enhancements
1. Improve performance of tool
2. Remove dependency on ArcGIS Desktop and the Spatial Analyst extension
3. Optimize candidate selection results based on additional criteria (e.g. proximity to ridge). 
4. Leverage "Big Data" tools to perform parrallel processing for each potential candidate