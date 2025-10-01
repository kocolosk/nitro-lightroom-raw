The goal of this project is to take an XMP file from Gentleman Coder's Nitro application, extract the crop and rotation metadata, and write that metadata back out into the format recognized by Adobe Lightroom.

Nitro and Lightroom both utilize XMP sidecars for Canon CR3 compressed RAW files. Schemas for Rating / Flag / Keyword metadata are consistent between the two products, so no translations are needed. Nitro stores crop and rotation metadata inside a plist, then stores that plist in the Nitro:EditModel attribute. Lightroom uses the Camera Raw Settings XML namespace. Moreover, the way the crop information is represented is quite different.

### Usage

1. Point Lightroom at a Nitro folder
2. Export all the images in this folder using "Original + Settings" to a new folder to create basic Lightroom-compatible XMPs. At this point, keywords / flags / ratings should be preserved, but no crop information (or other edits) will carry over.
3. Run the converter script on this new location and it will update the XMP files to port over the crops from Nitro's schema to CRS.